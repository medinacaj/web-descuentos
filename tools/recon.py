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
        out["final_url"] = r.final_url

    st = out["static"]
    hard_block = st.get("block") in ("cloudflare", "imperva", "perimeterx", "datadome", "captcha")
    if probe != "api" and use_browser and not st.get("has_data") and not hard_block:
        rr = await render(url)
        if rr["error"]:
            out["browser"] = {"error": rr["error"]}
        else:
            out["browser"] = detect.analyze_html(rr["html"], rr["status"], rr["final_url"], probe)

    out["verdict"], out["cause"] = verdict(out, probe)
    return out


def verdict(o: dict, probe: str) -> tuple[str, str]:
    st, br = o.get("static", {}), o.get("browser")
    if st.get("has_data"):
        return "ok", "API pública" if probe == "api" else "HTML estático"
    if br and br.get("has_data"):
        return "ok_js", "requiere navegador (JS dinámico)"
    for layer in (br, st):
        if not layer:
            continue
        if layer.get("block"):
            return "bloqueado", f"bloqueo/WAF ({layer['block']})"
        if layer.get("login"):
            return "login", "exige login/token"
    if st.get("error") and (not br or br.get("error")):
        return "no_alcanzable", st["error"][:120]
    status = (br or st).get("status")
    if status == 404:
        return "url_invalida", "404: la ruta de prueba no existe; corregir URL"
    if probe == "api":
        return "sin_datos", f"API sin resultados ({st.get('api_message') or status})"
    return "sin_datos", "la página carga pero no se detectan precios/beneficios"


def source_readable(source: dict, probes: list[dict]) -> tuple[str, str]:
    by = {p["probe"]: p for p in probes}
    good = {"ok", "ok_js"}
    main = "product" if source["kind"] in ("retail", "operador", "comparador") else "promos"
    main_ok = any(by.get(k, {}).get("verdict") in good for k in (main, "api"))
    others_ok = all(p["verdict"] in good for p in probes if p["probe"] not in (main, "api"))
    causes = "; ".join(f"{p['probe']}: {p['cause']}" for p in probes)
    if main_ok and others_ok:
        return "ok", causes
    if any(p["verdict"] in good for p in probes):
        return "partial", causes
    if all(p["verdict"] in ("bloqueado", "login", "robots") for p in probes):
        return "blocked", causes
    return "unknown" if all(p["verdict"] in ("no_alcanzable", "url_invalida") for p in probes) else "partial", causes


async def run(only: set[str] | None, use_browser: bool) -> dict:
    cfg = yaml.safe_load(SOURCES.read_text())
    client = PoliteClient(min_delay_s=4.0)
    results = []
    try:
        for s in cfg["sources"]:
            if only and s["id"] not in only:
                continue
            probes = []
            for name, url in (s.get("probes") or {}).items():
                print(f"[recon] {s['id']}:{name} {url}", file=sys.stderr, flush=True)
                probes.append(await probe_one(client, s, name, url, use_browser))
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
