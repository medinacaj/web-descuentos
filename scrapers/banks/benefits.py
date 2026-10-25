"""Fase 2 — extracción de beneficios desde páginas oficiales de emisores. Solo lo explícito en el texto.

Cada beneficio queda `confirmado`, `sin_confirmar` o `vencido` (ver `status_for`). Nada se infiere:
si el texto no dice el día, el tope o la vigencia, el campo queda en None.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser

PCT_RE = re.compile(r"(?<!\d)(\d{1,2})\s?%")
CLP_RE = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d{4,})")
DAYS = {"lunes": 1, "martes": 2, "miércoles": 3, "miercoles": 3, "jueves": 4, "viernes": 5, "sábado": 6, "sabado": 6, "domingo": 7}
DAY_RE = re.compile(r"\b(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bados?|domingos?)\b", re.I)
ALL_DAYS_RE = re.compile(r"todos\s+los\s+d[íi]as", re.I)
RANGE_RE = re.compile(r"de\s+(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)\s+a\s+(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)", re.I)
CAP_RE = re.compile(r"tope[^$\d]{0,40}\$\s?(\d{1,3}(?:\.\d{3})+|\d{4,})", re.I)
MIN_RE = re.compile(r"(?:compra|monto)\s+m[íi]nim[ao][^$\d]{0,20}\$\s?(\d{1,3}(?:\.\d{3})+|\d{4,})", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                          "septiembre", "octubre", "noviembre", "diciembre"])}
VALID_TXT_RE = re.compile(r"(?:hasta|v[áa]lid[oa] hasta|vigente hasta|vigencia hasta)\s+(?:el\s+)?(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+(?:de|del)\s+(\d{4}))?", re.I)
VALID_NUM_RE = re.compile(r"(?:hasta|v[áa]lid[oa] hasta|vigente hasta|vigencia hasta)\s+(?:el\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", re.I)
CHANNEL = [("online", re.compile(r"\bonline\b|sitio web|compras? por internet|e-?commerce", re.I)),
           ("presencial", re.compile(r"presencial|en tienda|en local", re.I)),
           ("app", re.compile(r"\bapp\b|aplicaci[óo]n", re.I))]
CARD_TYPE = [("credito", re.compile(r"cr[ée]dito", re.I)), ("debito", re.compile(r"d[ée]bito", re.I)),
             ("prepago", re.compile(r"prepago", re.I))]
STACK_NO = re.compile(r"no\s+(?:es\s+)?acumulable|no\s+se\s+acumula|no\s+aplica\s+con\s+otras", re.I)
STACK_YES = re.compile(r"(?<!no )acumulable con", re.I)
CONTAINER_HINT = re.compile(r"benef|promo|descuento|card|tarjeta|offer|item", re.I)


def _clp(s: str) -> int:
    return int(s.replace(".", ""))


def _days(text: str) -> list[int] | None:
    if ALL_DAYS_RE.search(text):
        return [1, 2, 3, 4, 5, 6, 7]
    m = RANGE_RE.search(text)
    if m:
        a, b = (DAYS[_norm_day(x)] for x in m.groups())
        return list(range(a, b + 1)) if a <= b else None
    found = sorted({DAYS[_norm_day(x)] for x in DAY_RE.findall(text)})
    return found or None


def _norm_day(s: str) -> str:
    s = s.lower().rstrip("s") if s.lower() not in ("lunes", "martes", "miércoles", "miercoles", "jueves", "viernes") else s.lower()
    return s


def _valid_to(text: str, today: date) -> date | None:
    m = VALID_NUM_RE.search(text)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        y = y + 2000 if y < 100 else y
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = VALID_TXT_RE.search(text)
    if m and m.group(2).lower() in MONTHS:
        y = int(m.group(3)) if m.group(3) else None
        if y is None:  # sin año no se adivina
            return None
        try:
            return date(y, MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            return None
    return None


def parse_benefit(text: str, issuer: str, source_url: str, terms_url: str | None, today: date) -> dict:
    t = re.sub(r"\s+", " ", text).strip()
    pcts = [int(x) for x in PCT_RE.findall(t)]
    cap = CAP_RE.search(t)
    mn = MIN_RE.search(t)
    stack = False if STACK_NO.search(t) else (True if STACK_YES.search(t) else None)
    b = {
        "issuer": issuer,
        "merchant": None,
        "percent": max(pcts) if pcts else None,
        "percent_note": "varios porcentajes en el texto; se usa el mayor" if len(set(pcts)) > 1 else None,
        "cap": _clp(cap.group(1)) if cap else None,
        "min_purchase": _clp(mn.group(1)) if mn else None,
        "weekdays": _days(t),
        "valid_to": _valid_to(t, today),
        "channel": next((c for c, rx in CHANNEL if rx.search(t)), None),
        "card_type": next((c for c, rx in CARD_TYPE if rx.search(t)), None),
        "stackable": stack,
        "terms_url": terms_url,
        "source_url": source_url,
        "text": t[:600],
    }
    return b


def status_for(b: dict, today: date) -> tuple[str, list[str]]:
    """confirmado: fuente oficial + % + comercio + (vigencia o días). vencido: vigencia pasada."""
    if b["valid_to"] and b["valid_to"] < today:
        return "vencido", ["vigencia pasada"]
    missing = []
    if b["percent"] is None:
        missing.append("sin porcentaje")
    if not b["merchant"]:
        missing.append("sin comercio identificado")
    if b["valid_to"] is None and b["weekdays"] is None:
        missing.append("sin vigencia ni días")
    return ("confirmado", []) if not missing else ("sin_confirmar", missing)


def benefit_blocks(html: str, page_url: str) -> list[dict]:
    """Bloques de la página que parecen un beneficio: un elemento con % y un título propio."""
    tree = LexborHTMLParser(html or "")
    for tag in tree.css("script, style, noscript, template, header, footer, nav"):
        tag.decompose()
    out, seen = [], set()
    for node in tree.css("article, li, div, section, a"):
        cls = (node.attributes.get("class") or "") + " " + (node.attributes.get("id") or "")
        text = node.text(separator=" ", strip=True)
        if not (20 <= len(text) <= 500) or not PCT_RE.search(text):
            continue
        if node.tag == "div" and not CONTAINER_HINT.search(cls):
            continue
        # el bloque más interno que cumple: si un hijo ya lo cumple, se prefiere el hijo
        if any(PCT_RE.search(c.text(separator=" ", strip=True) or "") and len(c.text(strip=True)) >= 20
               for c in node.iter() if c.tag in ("article", "li", "div", "section", "a")):
            continue
        key = re.sub(r"\W+", "", text.lower())[:160]
        if key in seen:
            continue
        seen.add(key)
        heading = node.css_first("h1, h2, h3, h4, h5, strong, b, [class*=title], [class*=nombre], [class*=name]")
        merchant = heading.text(strip=True) if heading else None
        if merchant and (PCT_RE.search(merchant) or len(merchant) > 60):
            merchant = None
        link = node.attributes.get("href") if node.tag == "a" else None
        if not link:
            a = node.css_first("a[href]")
            link = a.attributes.get("href") if a else None
        terms = None
        for a in node.css("a[href]"):
            if re.search(r"bases|t[ée]rminos|condiciones|legal|\.pdf", (a.text() or "") + (a.attributes.get("href") or ""), re.I):
                terms = urljoin(page_url, a.attributes.get("href"))
                break
        out.append({"text": text, "merchant": merchant, "link": urljoin(page_url, link) if link else None, "terms": terms})
    return out


def extract(html: str, page_url: str, issuer: str, today: date) -> list[dict]:
    res = []
    for blk in benefit_blocks(html, page_url):
        b = parse_benefit(blk["text"], issuer, blk["link"] or page_url, blk["terms"], today)
        b["merchant"] = blk["merchant"]
        b["status"], b["status_reasons"] = status_for(b, today)
        res.append(b)
    return res
