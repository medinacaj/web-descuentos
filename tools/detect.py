"""Heurísticas de la fase 0: ¿la respuesta trae datos útiles, está bloqueada o requiere login?

Solo describe lo que aparece en la respuesta; nunca rellena datos faltantes.
"""
from __future__ import annotations

import json
import re

from selectolax.lexbor import LexborHTMLParser as HTMLParser

BLOCK_MARKERS = {
    "cloudflare": ["cf-chl", "challenge-platform", "just a moment...", "attention required! | cloudflare"],
    "akamai": ["access denied</title>", "errors.edgesuite.net", "_abck"],
    "imperva": ["_incapsula_resource", "incapsula incident"],
    "perimeterx": ["px-captcha", "_pxappid"],
    "datadome": ["captcha-delivery.com", "datadome"],
    "captcha": ["g-recaptcha", "hcaptcha.com", "are you a robot", "eres un robot"],
}
LOGIN_MARKERS = ["account-verification", "iniciar sesión para continuar", "debes iniciar sesión", "ingresa a tu cuenta para ver",
                 "/login?redirect", "please log in"]

# $1.299.990 / $ 1.299.990 / CLP 1.299.990
CLP_RE = re.compile(r"(?:\$|CLP)\s?(\d{1,3}(?:\.\d{3})+)")
PCT_RE = re.compile(r"\b(\d{1,2})\s?%\s?(?:dcto|de descuento|descuento|off|cashback|de dcto)?", re.I)
PROMO_WORDS_RE = re.compile(r"\b(dcto|descuento|beneficio|cashback|cuotas sin inter[eé]s|2x1)\b", re.I)
SAMPLE_RE = re.compile(r"iphone\s*15\s*pro(?!\s*max)", re.I)


def parse_clp(s: str) -> int:
    return int(s.replace(".", ""))


def visible_text(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script, style, noscript, template"):
        tag.decompose()
    body = tree.body or tree.root
    return re.sub(r"\s+", " ", body.text(separator=" ") if body else "")


def detect_waf(html: str) -> str | None:
    """Proveedor anti-bot presente en la página (informativo: su script aparece también en páginas sanas)."""
    low = html[:200_000].lower()
    for vendor, marks in BLOCK_MARKERS.items():
        if any(m in low for m in marks):
            return vendor
    return None


def detect_block(html: str, status: int | None, text_chars: int) -> str | None:
    """Bloqueo real: 401/403/429/503, o una página de desafío (marcador anti-bot + casi sin contenido)."""
    waf = detect_waf(html)
    if status in (401, 403, 429, 503):
        return waf or f"http_{status}"
    if waf and status == 200 and text_chars < 800:
        return waf
    return None


def detect_login(html: str, final_url: str) -> bool:
    low = html[:200_000].lower()
    return any(m in low for m in LOGIN_MARKERS) or bool(
        re.search(r"/(login|signin|ingresar|account-verification)\b", final_url, re.I))


def is_not_found(status: int | None, final_url: str) -> bool:
    return status == 404 or bool(re.search(r"/(not-found|404)\b", final_url, re.I))


def jsonld_offers(html: str) -> list[dict]:
    """Productos con oferta y precio en JSON-LD (schema.org)."""
    out: list[dict] = []
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text(strip=True) or "null")
        except (json.JSONDecodeError, ValueError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
                continue
            if not isinstance(d, dict):
                continue
            stack.extend(v for k, v in d.items() if k in ("@graph", "itemListElement", "item"))
            if d.get("@type") in ("Product", ["Product"]) and d.get("offers"):
                offers = d["offers"]
                offers = offers if isinstance(offers, list) else [offers]
                for o in offers:
                    price = o.get("price") or o.get("lowPrice")
                    if price is not None:
                        out.append({"name": d.get("name"), "price": price,
                                    "currency": o.get("priceCurrency"), "availability": o.get("availability")})
    return out


def embedded_state(html: str) -> list[str]:
    found = []
    for marker in ("__NEXT_DATA__", "__NUXT__", "__PRELOADED_STATE__", "__INITIAL_STATE__", "window.__STATE__",
                   "__APOLLO_STATE__", "vtex", "dataLayer"):
        if marker in html:
            found.append(marker)
    return found


def sample_items(text: str, limit: int = 3) -> list[dict]:
    """Pares (texto de 'iPhone 15 Pro …', primer precio CLP a ≤250 caracteres). Evidencia, no dato final."""
    out = []
    for m in SAMPLE_RE.finditer(text):
        window = text[m.start(): m.start() + 250]
        p = CLP_RE.search(window)
        if not p:
            continue
        title = window[: p.start()].strip()[:120]
        item = {"title": title, "price": parse_clp(p.group(1))}
        if item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def analyze_html(html: str, status: int | None, final_url: str, probe: str) -> dict:
    text = visible_text(html) if html else ""
    prices = [parse_clp(x) for x in CLP_RE.findall(text)]
    res = {
        "status": status,
        "final_url": final_url,
        "bytes": len(html),
        "text_chars": len(text),
        "waf": detect_waf(html) if html else None,
        "block": detect_block(html, status, len(text)) if html or status else None,
        "login": detect_login(html, final_url) if html else False,
        "not_found": is_not_found(status, final_url),
        "jsonld_offers": jsonld_offers(html)[:5] if html else [],
        "embedded_state": embedded_state(html) if html else [],
        "clp_prices_in_text": len(prices),
        "samples": sample_items(text) if probe == "product" else [],
        "promo_pct_hits": len(PCT_RE.findall(text)),
        "promo_word_hits": len(PROMO_WORDS_RE.findall(text)),
    }
    res["has_data"] = has_data(res, probe)
    # Precios presentes pero sin el producto de ejemplo: legible, pero la búsqueda no quedó demostrada.
    res["generic_prices"] = probe == "product" and not res["has_data"] and usable(res) and len(prices) >= 3
    return res


def usable(res: dict) -> bool:
    return not (res["block"] or res["login"] or res["not_found"] or (res["status"] or 0) >= 400)


def has_data(res: dict, probe: str) -> bool:
    if not usable(res):
        return False
    if probe == "product":
        return bool(res["samples"] or res["jsonld_offers"])
    if probe == "promos":
        return res["promo_pct_hits"] >= 3 or res["promo_word_hits"] >= 5
    return False


def analyze_api(body: str, status: int | None, source_id: str) -> dict:
    res = {"status": status, "bytes": len(body), "block": None, "login": False, "samples": [], "has_data": False}
    if status in (401, 403):
        res["block"] = f"http_{status}"
        res["login"] = True  # APIs que exigen token
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        res["error"] = "respuesta no es JSON"
        return res
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list) and results:
        for r in results[:3]:
            if source_id == "mercadolibre":
                res["samples"].append({"title": r.get("title"), "price": r.get("price"),
                                       "condition": r.get("condition"), "seller_id": (r.get("seller") or {}).get("id")})
            else:
                res["samples"].append({"title": r.get("name") or r.get("title"), "id": r.get("id")})
        # La API responde; solo cuenta como dato si la búsqueda realmente filtró el producto de ejemplo.
        res["has_data"] = any(SAMPLE_RE.search(str(x.get("title") or "")) for x in res["samples"])
        res["generic_prices"] = not res["has_data"]
    elif isinstance(data, dict):
        res["api_message"] = str(data.get("message") or data.get("error") or "")[:200]
    return res
