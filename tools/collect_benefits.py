"""Fase 2 — recolecta beneficios de emisores (BCI, MACH, Tenpo) y los clasifica por estado de verificación.

No escribe en la base de datos ni envía correos. Uso:
  python -m tools.collect_benefits [--only mach] [--no-browser] [--out reports/benefits.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from selectolax.lexbor import LexborHTMLParser

from scrapers.banks import benefits as bn
from scrapers.base import PoliteClient

ROOT = Path(__file__).resolve().parent.parent
PILOT = {"bci": "BCI", "mach": "MACH", "tenpo": "Tenpo"}
BLOCK = (401, 403, 429)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def diagnose(html: str) -> dict:
    tree = LexborHTMLParser(html or "")
    pct_nodes = [n for n in tree.css("article, li, div, section, a") if bn.PCT_RE.search(n.text(strip=True) or "")]
    classes = Counter(c for n in pct_nodes for c in (n.attributes.get("class") or "").split()[:2])
    return {"bytes": len(html), "nodes_with_pct": len(pct_nodes), "top_classes": classes.most_common(8),
            "iframes": [i.attributes.get("src") for i in tree.css("iframe[src]")][:3]}


async def page_html(client: PoliteClient, url: str, use_browser: bool) -> tuple[str, str, list[str]]:
    notes = []
    if await client.robots_allows(url) is False:
        return "", "robots", ["robots.txt prohíbe la ruta"]
    r = await client.get(url)
    if r.error:
        return "", "error", [r.error]
    if r.status in BLOCK:
        return "", "bloqueado", [f"HTTP {r.status}: se detiene sin reintentos ni evasión"]
    html, mode = r.text, "html"
    if use_browser and not bn.benefit_blocks(html, r.final_url):
        from tools.recon import render
        rr = await render(url)
        if rr["error"]:
            notes.append("navegador: " + rr["error"])
        elif rr["status"] in BLOCK:
            return "", "bloqueado", [f"navegador HTTP {rr['status']}"]
        else:
            html, mode = rr["html"], "navegador"
    return html, mode, notes


async def run(only: set[str] | None, use_browser: bool, today: date) -> tuple[list[dict], list[dict]]:
    registry = {s["id"]: s for s in yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["sources"]}
    client = PoliteClient(min_delay_s=4.0)
    all_b, stats = [], []
    try:
        for sid, issuer in PILOT.items():
            if only and sid not in only:
                continue
            url = registry[sid]["probes"]["promos"]
            log(f"[benefits] {sid}: {url}")
            html, mode, notes = await page_html(client, url, use_browser)
            found = bn.extract(html, url, issuer, today) if html else []
            st = {"source_id": sid, "issuer": issuer, "url": url, "mode": mode, "count": len(found),
                  "by_status": dict(Counter(b["status"] for b in found)), "notes": notes}
            if html and len(found) < 3:
                st["diagnose"] = diagnose(html)
            stats.append(st)
            for b in found:
                b["source_id"] = sid
            all_b += found
    finally:
        await client.close()
    return all_b, stats


def summary(benefits: list[dict], stats: list[dict]) -> str:
    lines = ["# Beneficios fase 2", f"Comprobado: {datetime.now(timezone.utc).isoformat(timespec='seconds')} · "
             f"runner: {os.environ.get('RUNNER_NAME', 'local')}", "",
             "| Emisor | Lectura | Beneficios | Confirmados | Sin confirmar | Vencidos |", "|---|---|---|---|---|---|"]
    for s in stats:
        bs = s["by_status"]
        lines.append(f"| {s['issuer']} | {s['mode']} | {s['count']} | {bs.get('confirmado', 0)} | "
                     f"{bs.get('sin_confirmar', 0)} | {bs.get('vencido', 0)} |")
    reasons = Counter(r for b in benefits for r in b["status_reasons"])
    lines += ["", "## Motivos de no confirmación", ""] + [f"- {r} ×{n}" for r, n in reasons.most_common()]
    lines += ["", "## Muestra de confirmados (hasta 10)", ""]
    for b in [b for b in benefits if b["status"] == "confirmado"][:10]:
        days = ",".join(map(str, b["weekdays"])) if b["weekdays"] else "—"
        lines.append(f"- {b['issuer']} · {b['merchant']} · {b['percent']}% · días {days} · tope {b['cap'] or 'no informado'} "
                     f"· vigencia {b['valid_to'] or '—'} · {b['card_type'] or 'tarjeta no especificada'}")
    lines += ["", "## Muestra de textos sin confirmar (hasta 6)", ""]
    for b in [b for b in benefits if b["status"] == "sin_confirmar"][:6]:
        lines.append(f"- {b['issuer']}: {b['text'][:160]!r} → {', '.join(b['status_reasons'])}")
    lines += ["", "## Notas y diagnóstico", ""]
    for s in stats:
        for n in s["notes"]:
            lines.append(f"- {s['issuer']}: {n}")
        if s.get("diagnose"):
            lines.append(f"- {s['issuer']}: pocos bloques · {s['diagnose']}")
    lines += ["", "_Muestra de recolección: no es un listado vigente de beneficios._"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--out", default="reports/benefits.json")
    a = ap.parse_args()
    today = datetime.now(ZoneInfo("America/Santiago")).date()
    benefits, stats = asyncio.run(run(set(a.only.split(",")) if a.only else None, not a.no_browser, today))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"checked_on": today.isoformat(), "benefits": benefits, "stats": stats},
                              ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")
    md = summary(benefits, stats)
    if p := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(p).write_text(md)
    print(md)


if __name__ == "__main__":
    main()
