"""Fase 0 — reconocimiento de fuentes. NO es un scraper definitivo.

Para cada fuente de config/sources.yaml prueba sus URLs (producto de ejemplo, promociones, API si existe):
  1. robots.txt  → si prohíbe la ruta, no se pide.
  2. httpx       → HTML estático.
  3. Playwright  → solo si el HTML estático no trae datos y no hubo bloqueo duro.
Escribe reports/recon_<fecha>.json, reports/readability_map.md y (con --write-sources) el campo readable.

Uso:  python -m tools.recon [--only falabella,bci] [--no-browser] [--write-sources]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from scrapers.base import PoliteClient
from tools import detect

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "config" / "sources.yaml"
REPORTS = ROOT / "reports"
TZ = ZoneInfo("America/Santiago")


async def render(url: str) -> dict:
    """Renderiza con Chromium headless. Devuelve html, status y url final."""
    from playwright.async_api import async_playwright

    exe = os.environ.get("CHROMIUM_PATH")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=exe or None)
        ctx = await browser.new_context(user_agent=detect_ua(), locale="es-CL", timezone_id="America/Santiago",
                                        viewport={"width": 1366, "height": 900})
        page = await ctx.new_page()
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            for _ in range(3):  # contenido perezoso
                await page.mouse.wheel(0, 2500)
                await page.wait_for_timeout(1200)
            return {"html": await page.content(), "status": resp.status if resp else None,
                    "final_url": page.url, "error": None}
        except Exception as e:  # noqa: BLE001 — se reporta tal cual
            return {"html": "", "status": None, "final_url": url, "error": f"{type(e).__name__}: {e}"[:300]}
        finally:
            await browser.close()


def detect_ua() -> str:
    from scrapers.base import USER_AGENT
    return USER_AGENT


GOOD = ("ok", "ok_js")
RANK = {"ok": 0, "ok_js": 1, "precios_sin_muestra": 2, "sin_datos": 3, "login": 4, "bloqueado": 5,
        "url_invalida": 6, "robots": 7, "no_alcanzable": 8}
SEARCH_INPUTS = ("q", "Ntt", "search", "s", "query", "valor", "term", "k", "text", "busqueda")
PROMO_LINK_RE = re.compile(r"beneficio|oferta|promoci|descuento|cyber|liquidaci|cupon", re.I)


async def probe_one(client: PoliteClient, source: dict, probe: str, url: str, use_browser: bool) -> dict:
    out: dict = {"probe": probe, "url": url}
    allowed = await client.robots_allows(url)
    out["robots"] = {True: "permitido", False: "prohibido", None: "no_disponible"}[allowed]
    if allowed is False:
        out.update(verdict="robots", cause="robots.txt prohíbe la ruta; no se pidió")
        return out

    r = await client.get(url)
    if r.error:
        out["static"] = {"error": r.error}
    elif probe == "api":
        out["static"] = detect.analyze_api(r.text, r.status, source["id"])
    else:
        out["static"] = detect.analyze_html(r.text, r.status, r.final_url, probe)

    st = out["static"]
    if probe != "api" and use_browser and not st.get("has_data") and not st.get("block") \
            and not st.get("not_found") and not st.get("error"):
        rr = await render(url)
        out["browser"] = {"error": rr["error"]} if rr["error"] else \
            detect.analyze_html(rr["html"], rr["status"], rr["final_url"], probe)
        out["_html"] = rr.get("html", "")
    out["_static_html"] = r.text if not r.error else ""
    out["verdict"], out["cause"] = verdict(out, probe)
    return out


def verdict(o: dict, probe: str) -> tuple[str, str]:
    st, br = o.get("static", {}), o.get("browser")
    if st.get("has_data"):
        return "ok", "API pública" if probe == "api" else "HTML estático"
    if br and br.get("has_data"):
        return "ok_js", "requiere navegador (JS dinámico)"
    for layer in (st, br):
        if not layer:
            continue
        if layer.get("block"):
            return "bloqueado", f"bloqueo/WAF ({layer['block']}, HTTP {layer.get('status')})"
        if layer.get("login"):
            return "login", "exige login/verificación de cuenta o token"
        if layer.get("not_found"):
            return "url_invalida", "404/not-found: la ruta de prueba no existe"
    for layer in (br, st):
        if layer and layer.get("generic_prices"):
            how = "con navegador" if layer is br else "HTML estático"
            return "precios_sin_muestra", f"lee precios ({how}) pero no apareció el producto de ejemplo"
    if st.get("error") and (not br or br.get("error")):
        return "no_alcanzable", st["error"][:120]
    return "sin_datos", "la página carga pero no se detectan precios/beneficios"


def discover(html: str, base: str, probe: str, query: str) -> list[str]:
    """Busca en la portada el formulario de búsqueda (producto) o enlaces de promociones."""
    from urllib.parse import urljoin, urlsplit, quote_plus
    from selectolax.lexbor import LexborHTMLParser

    tree = LexborHTMLParser(html or "")
    host = urlsplit(base).netloc.split(".", 1)[-1]  # dominio sin subdominio
    found: list[str] = []
    if probe == "product":
        for form in tree.css("form"):
            for inp in form.css("input"):
                name = inp.attributes.get("name") or ""
                if (inp.attributes.get("type") == "search" and name) or name in SEARCH_INPUTS:
                    action = urljoin(base + "/", form.attributes.get("action") or "")
                    found.append(f"{action}{'&' if '?' in action else '?'}{name}={quote_plus(query)}")
                    break
    else:
        for a in tree.css("a[href]"):
            href = urljoin(base + "/", a.attributes.get("href") or "")
            label = (a.text() or "") + " " + href
            if PROMO_LINK_RE.search(label) and host in urlsplit(href).netloc and href not in found:
                found.append(href.split("#")[0])
    return found[:2]


async def probe_with_discovery(client, source, probe, url, use_browser, query, home_cache) -> dict:
    res = await probe_one(client, source, probe, url, use_browser)
    if probe == "api" or res["verdict"] in GOOD + ("bloqueado", "login", "robots", "no_alcanzable"):
        return strip(res)
    base = source["base_url"].rstrip("/")
    if base not in home_cache:
        h = await client.get(base)
        html = h.text if not h.error else ""
        cands = discover(html, base, "product", query) + discover(html, base, "promos", query)
        if use_browser and not cands and not h.error and h.status == 200:
            html = (await render(base))["html"]
        home_cache[base] = html
    for cand in discover(home_cache[base], base, probe, query):
        if cand == url:
            continue
        print(f"[recon]   descubierta {probe}: {cand}", file=sys.stderr, flush=True)
        alt = await probe_one(client, source, probe, cand, use_browser)
        if RANK[alt["verdict"]] < RANK[res["verdict"]]:
            alt["discovered_from"] = base
            alt["first_try"] = {"url": url, "verdict": res["verdict"], "cause": res["cause"]}
            res = alt
        if res["verdict"] in GOOD:
            break
    return strip(res)


def strip(res: dict) -> dict:
    res.pop("_html", None)
    res.pop("_static_html", None)
    return res


def source_readable(source: dict, probes: list[dict]) -> tuple[str, str]:
    by = {p["probe"]: p for p in probes}
    main = "product" if source["kind"] in ("retail", "operador", "comparador") else "promos"
    main_ok = any(by.get(k, {}).get("verdict") in GOOD for k in (main, "api"))
    others_ok = all(p["verdict"] in GOOD for p in probes if p["probe"] not in (main, "api"))
    causes = "; ".join(f"{p['probe']}: {p['cause']}" for p in probes)
    if main_ok and others_ok:
        return "ok", causes
    if any(p["verdict"] in GOOD + ("precios_sin_muestra",) for p in probes):
        return "partial", causes
    if all(p["verdict"] in ("bloqueado", "login", "robots") for p in probes):
        return "blocked", causes
    if all(p["verdict"] in ("no_alcanzable", "url_invalida") for p in probes):
        return "unknown", causes
    return "partial", causes


async def run(only: set[str] | None, use_browser: bool) -> dict:
    cfg = yaml.safe_load(SOURCES.read_text())
    client = PoliteClient(min_delay_s=4.0)
    query = cfg.get("defaults", {}).get("sample_query", "iphone 15 pro 256gb")
    home_cache: dict[str, str] = {}
    results = []
    try:
        for s in cfg["sources"]:
            if only and s["id"] not in only:
                continue
            probes = []
            for name, url in (s.get("probes") or {}).items():
                print(f"[recon] {s['id']}:{name} {url}", file=sys.stderr, flush=True)
                probes.append(await probe_with_discovery(client, s, name, url, use_browser, query, home_cache))
            readable, causes = source_readable(s, probes)
            results.append({"id": s["id"], "name": s["name"], "kind": s["kind"], "readable": readable,
                            "causes": causes, "probes": probes})
    finally:
        await client.close()
    return {"checked_at": datetime.now(TZ).isoformat(timespec="seconds"),
            "runner": os.environ.get("RUNNER_NAME", "local"), "sources": results}


ICON = {"ok": "🟢 ok", "partial": "🟡 parcial", "blocked": "🔴 bloqueado", "unknown": "⚪ desconocido"}


def to_markdown(rep: dict) -> str:
    rs = rep["sources"]
    count = {k: sum(r["readable"] == k for r in rs) for k in ICON}
    lines = [f"# Mapa de legibilidad — fase 0",
             f"Comprobado: {rep['checked_at']} (America/Santiago) · runner: {rep['runner']}",
             f"Fuentes revisadas: **{len(rs)}** · " + " · ".join(f"{ICON[k]}: {v}" for k, v in count.items()), "",
             "| Fuente | Tipo | Legible | Producto | Promos | API | Evidencia |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        by = {p["probe"]: p for p in r["probes"]}
        cell = lambda k: (f"{by[k]['verdict']}" if k in by else "—")  # noqa: E731
        ev = ""
        for p in r["probes"]:
            layer = p.get("browser") if p.get("browser", {}).get("has_data") else p.get("static", {})
            if layer and layer.get("samples"):
                s0 = layer["samples"][0]
                ev = f"{(s0.get('title') or '')[:50]} → {s0.get('price', '')}"
                break
            if layer and p["probe"] == "promos" and layer.get("has_data"):
                ev = f"{layer['promo_pct_hits']} menciones de % / {layer['promo_word_hits']} de dcto/beneficio"
        lines.append(f"| {r['name']} | {r['kind']} | {ICON[r['readable']]} | {cell('product')} | {cell('promos')} "
                     f"| {cell('api')} | {ev.replace('|', '/')} |")
    lines += ["", "## Causas por fuente", ""]
    for r in rs:
        lines.append(f"- **{r['name']}**: {r['causes']}")
        for p in r["probes"]:
            if p.get("first_try"):
                lines.append(f"  - {p['probe']}: URL descubierta {p['url']} (la configurada dio {p['first_try']['verdict']})")
    lines += ["", "_Las muestras de precio son evidencia de legibilidad, no precios validados para alertas._"]
    return "\n".join(lines) + "\n"


def write_sources(rep: dict) -> None:
    """Actualiza readable/readable_cause en sources.yaml sin perder comentarios."""
    by = {r["id"]: r for r in rep["sources"]}
    out, cur = [], None
    for line in SOURCES.read_text().splitlines():
        m = re.match(r"\s*- id: (\S+)", line)
        if m:
            cur = m.group(1)
        if cur in by and re.match(r"\s+readable_cause:", line):
            continue
        if cur in by and re.match(r"\s+readable:", line):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}readable: {by[cur]['readable']}")
            out.append(f"{indent}readable_cause: {json.dumps(by[cur]['causes'], ensure_ascii=False)}")
            continue
        out.append(line)
    SOURCES.write_text("\n".join(out) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="ids separados por coma")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--write-sources", action="store_true")
    a = ap.parse_args()
    rep = asyncio.run(run(set(a.only.split(",")) if a.only else None, not a.no_browser))
    REPORTS.mkdir(exist_ok=True)
    day = rep["checked_at"][:10]
    (REPORTS / f"recon_{day}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2))
    md = to_markdown(rep)
    (REPORTS / "readability_map.md").write_text(md)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary).write_text(md)
    if a.write_sources:
        write_sources(rep)
    print(md)


if __name__ == "__main__":
    main()
