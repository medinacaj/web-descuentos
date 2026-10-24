"""Fase 1 — recolecta fichas de producto de las fuentes piloto y las valida con core/verify.py.

No envía correos ni escribe en la base de datos. Uso:
  python -m tools.collect [--only hites] [--max 8] [--out reports/collected.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.pricing import grouped_offers
from scrapers.base import PoliteClient
from scrapers.retail import product as prod

ROOT = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def pilot_sources(only: set[str] | None) -> list[dict]:
    pilot = json.loads((ROOT / "config" / "phase1_sources.json").read_text(encoding="utf8"))
    registry = {s["id"]: s for s in yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["sources"]}
    out = []
    for s in pilot["sources"]:
        if only and s["id"] not in only:
            continue
        out.append({"id": s["id"], "search_url": registry[s["id"]]["probes"]["product"]})
    return out


async def collect_source(client: PoliteClient, src: dict, max_items: int) -> tuple[list[dict], dict]:
    sid, url = src["id"], src["search_url"]
    stats = {"source_id": sid, "search_url": url, "links": 0, "fetched": 0, "errors": []}
    if await client.robots_allows(url) is False:
        stats["errors"].append("robots.txt prohíbe la búsqueda")
        return [], stats
    r = await client.get(url)
    if r.error or r.status != 200:
        stats["errors"].append(f"búsqueda: {r.error or 'HTTP ' + str(r.status)}")
        return [], stats
    links = prod.product_links(r.text, r.final_url, sid, limit=max_items)
    stats["links"] = len(links)
    if not links:
        stats["search_diagnose"] = prod.diagnose(r.text)
    records = []
    for link in links:
        if await client.robots_allows(link) is False:
            stats["errors"].append(f"robots prohíbe {link}")
            continue
        p = await client.get(link)
        captured = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if p.error or p.status != 200:
            stats["errors"].append(f"ficha {link}: {p.error or 'HTTP ' + str(p.status)}")
            if p.status in (401, 403, 429):
                stats["errors"].append("fichas bloqueadas: se detiene esta tienda (sin reintentos ni evasión)")
                break
            continue
        stats["fetched"] += 1
        rec = prod.parse_product(p.text, p.final_url, sid, captured)
        if rec["extraction"] == "ninguna" or not rec["seller"]:
            rec["diagnose"] = prod.diagnose(p.text)
        records.append(rec)
    return records, stats


async def run(only: set[str] | None, max_items: int) -> tuple[list[dict], list[dict]]:
    client = PoliteClient(min_delay_s=4.0)
    records, stats = [], []
    try:
        for src in pilot_sources(only):
            log(f"[collect] {src['id']}: {src['search_url']}")
            recs, st = await collect_source(client, src, max_items)
            records += recs
            stats.append(st)
    finally:
        await client.close()
    return records, stats


def summary(records: list[dict], stats: list[dict], checked: dict) -> str:
    acc = Counter(x["source_id"] for xs in checked["verified_by_condition"].values() for x in xs)
    rej: dict[str, Counter] = {}
    for x in checked["rejected"]:
        rej.setdefault(x["source_id"], Counter())[x["reason"]] += 1
    lines = ["# Recolección fase 1",
             f"Comprobado: {datetime.now(timezone.utc).isoformat(timespec='seconds')} · runner: "
             f"{os.environ.get('RUNNER_NAME', 'local')}", "",
             "| Fuente | Enlaces | Fichas leídas | Aceptadas | Rechazos |", "|---|---|---|---|---|"]
    for st in stats:
        sid = st["source_id"]
        r = ", ".join(f"{k} ×{v}" for k, v in rej.get(sid, Counter()).most_common()) or "—"
        lines.append(f"| {sid} | {st['links']} | {st['fetched']} | {acc.get(sid, 0)} | {r} |")
    lines += ["", "## Aceptadas por condición (precio de la ficha, sin beneficios ni despacho)", ""]
    for cond, xs in checked["verified_by_condition"].items():
        for x in xs:
            lines.append(f"- {cond} · {x['source_id']} · {x['price_clp']:,} CLP · vendedor: {x.get('seller') or 'no informado'} "
                         f"· {x['title']} · {x['url']}".replace(",", "."))
    lines += ["", "## Errores y diagnóstico", ""]
    for st in stats:
        for e in st["errors"]:
            lines.append(f"- {st['source_id']}: {e}")
        if st.get("search_diagnose"):
            lines.append(f"- {st['source_id']}: búsqueda sin enlaces · {st['search_diagnose']}")
    for rec in records:
        if rec.get("diagnose") or rec["notes"]:
            lines.append(f"- {rec['source_id']} {rec['url']}: {'; '.join(rec['notes'])}"
                         + (f" · {rec['diagnose']}" if rec.get("diagnose") else ""))
    lines += ["", "_Muestra de recolección: no son alertas ni precios finales pagaderos._"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="ids separados por coma")
    ap.add_argument("--max", type=int, default=8, help="fichas por tienda")
    ap.add_argument("--out", default="reports/collected.json")
    a = ap.parse_args()
    records, stats = asyncio.run(run(set(a.only.split(",")) if a.only else None, a.max))
    checked = grouped_offers(records)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"records": records, "stats": stats, "checked": checked},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    md = summary(records, stats, checked)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(path).write_text(md)
    print(md)


if __name__ == "__main__":
    main()
