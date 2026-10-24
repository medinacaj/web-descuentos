"""Extracción de fichas de producto (fase 1). Solo hechos presentes en la página; lo ausente queda en None.

Flujo: búsqueda → enlaces a fichas del modelo → ficha → registro para core/verify.py.
"""
from __future__ import annotations

import json
import re
from collections import deque
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser

# Rutas de ficha conocidas por tienda. Si una tienda cambia de formato, el slug con el modelo sirve de respaldo.
PRODUCT_PATH = {
    "falabella": re.compile(r"/falabella-cl/product/\d+", re.I),
    "hites": re.compile(r"-\d{8,}\.html$", re.I),
    "lider": re.compile(r"/ip/", re.I),
}
DOMAIN = {"falabella": "falabella.com", "hites": "hites.com", "lider": "lider.cl"}
MODEL_RE = re.compile(r"iphone[\s\-_]*15[\s\-_]*pro(?![\s\-_]*max)", re.I)
STORAGE_RE = re.compile(r"(?<![\d+])(128|256|512)[\s\-_]*gb|\b1[\s\-_]*tb\b", re.I)

# Condición desde el título: tiene prioridad sobre schema.org porque algunos vendedores marcan
# NewCondition en equipos reacondicionados. Términos ambiguos ("grado A", "open box") no confirman nada.
TITLE_CONDITION = [
    ("reacondicionado", re.compile(r"reacondicionad|refurbished|renewed", re.I)),
    ("seminuevo", re.compile(r"semi[\s\-]?nuevo", re.I)),
    ("usado", re.compile(r"\busad[oa]\b|\bused\b", re.I)),
    ("exhibicion", re.compile(r"exhibici[oó]n|open[\s\-]?box", re.I)),
]
NEW_RE = re.compile(r"\bnuevo\b|\bsellado\b|\bnew\b", re.I)
AMBIGUOUS_RE = re.compile(r"\bgrad[eo]\s*[a-c]\b|\bclase\s*[a-c]\b|\bcpo\b", re.I)
SCHEMA_CONDITION = {
    "newcondition": "nuevo",
    "refurbishedcondition": "reacondicionado",
    "usedcondition": "usado",
    "damagedcondition": "usado",
}
AVAILABILITY = {"instock": True, "limitedavailability": True, "onlineonly": True,
                "outofstock": False, "soldout": False, "discontinued": False, "preorder": False}


def _tail(v) -> str:
    return str(v or "").rstrip("/").rsplit("/", 1)[-1].lower()


def _json_scripts(tree: LexborHTMLParser) -> tuple[list, object | None]:
    lds = []
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            lds.append(json.loads(node.text(strip=True) or "null"))
        except (json.JSONDecodeError, ValueError):
            continue
    nxt = tree.css_first("script#__NEXT_DATA__")
    state = None
    if nxt:
        try:
            state = json.loads(nxt.text(strip=True))
        except (json.JSONDecodeError, ValueError):
            state = None
    return lds, state


def _walk(obj):
    """Recorrido en anchura: conserva el orden de aparición."""
    stack = deque([obj])
    while stack:
        d = stack.popleft()
        if isinstance(d, dict):
            yield d
            stack.extend(d.values())
        elif isinstance(d, list):
            stack.extend(d)


def _is_type(d: dict, name: str) -> bool:
    t = d.get("@type")
    return t == name or (isinstance(t, list) and name in t)


# ----------------------------------------------------------------------------- búsqueda
def product_links(html: str, page_url: str, source_id: str, limit: int = 8) -> list[str]:
    """Enlaces a fichas del modelo buscado (sin Pro Max), en orden de aparición, sin duplicados."""
    tree = LexborHTMLParser(html or "")
    lds, state = _json_scripts(tree)
    cands: list[tuple[str, str]] = []
    for a in tree.css("a[href]"):
        cands.append((a.attributes.get("href") or "", a.text(separator=" ") or ""))
    for blob in lds + ([state] if state else []):
        for d in _walk(blob):
            url = d.get("url") or d.get("productUrl") or d.get("canonicalUrl") or d.get("@id")
            name = d.get("name") or d.get("displayName") or d.get("productName") or ""
            if isinstance(url, str) and isinstance(name, str):
                cands.append((url, name))
    out: list[str] = []
    seen: set[str] = set()
    for href, label in cands:
        url = urljoin(page_url, href.strip()).split("#")[0]
        parts = urlsplit(url)
        if parts.scheme != "https" or not (parts.hostname or "").endswith(DOMAIN[source_id]):
            continue
        path = parts.path
        known = bool(PRODUCT_PATH[source_id].search(path))
        slug_model = MODEL_RE.search(path.replace("/", " "))
        label_model = MODEL_RE.search(label)
        text = path + " " + label
        if re.search(r"pro[\s\-_]*max", text, re.I):
            continue
        storages = {re.sub(r"[\s\-_]", "", m.group(0).lower()) for m in STORAGE_RE.finditer(text)}
        if storages and storages != {"256gb"}:
            continue  # otra capacidad: no se pide la ficha
        if (known and (label_model or slug_model)) or (slug_model and re.search(r"\d{6,}", path)):
            clean = parts._replace(fragment="").geturl()
            key = product_key(clean)
            if key not in seen:
                seen.add(key)
                out.append(clean)
        if len(out) >= limit:
            break
    return out


def product_key(url: str) -> str:
    """Identificador de ficha: Falabella repite la misma ficha con y sin SKU al final."""
    m = re.search(r"/product/(\d+)", url)
    return m.group(1) if m else urlsplit(url)._replace(query="").geturl()


# ----------------------------------------------------------------------------- ficha
def condition_from(title: str, schema_value) -> tuple[str | None, str]:
    for cond, rx in TITLE_CONDITION:
        if rx.search(title):
            return cond, "título"
    if NEW_RE.search(title):
        return "nuevo", "título"
    if AMBIGUOUS_RE.search(title):
        return None, "título ambiguo (grado/clase sin condición explícita)"
    mapped = SCHEMA_CONDITION.get(_tail(schema_value))
    if mapped == "nuevo":
        # NewCondition es el valor por omisión de muchas plataformas; sin texto que lo diga no prueba nada.
        return None, "solo schema.org NewCondition, sin 'nuevo' en el título"
    if mapped:
        return mapped, "schema.org itemCondition"
    return None, "sin condición explícita"


def _price_int(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v) if v > 0 and float(v).is_integer() else None
    if isinstance(v, str):
        s = v.strip().replace("$", "").replace(" ", "")
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            return int(s.replace(".", ""))
        if re.fullmatch(r"\d+(\.0+)?", s):
            return int(float(s)) or None
    return None


def parse_product(html: str, url: str, source_id: str, captured_at: str) -> dict:
    """Registro en el formato de core/verify.py, más `notes` con lo que faltó."""
    tree = LexborHTMLParser(html or "")
    lds, state = _json_scripts(tree)
    product = next((d for blob in lds for d in _walk(blob) if _is_type(d, "Product")), None)
    rec = {"source_id": source_id, "url": url, "title": None, "condition": None, "currency": None,
           "price_clp": None, "in_stock": None, "seller": None, "price_evidence": None,
           "captured_at": captured_at, "extraction": "json-ld", "notes": []}
    if not product:
        rec["extraction"] = "ninguna"
        rec["notes"].append("la ficha no trae JSON-LD Product")
        return rec

    rec["title"] = str(product.get("name") or "").strip() or None
    offers = product.get("offers")
    offers = offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []
    # AggregateOffer agrupa vendedores: no se puede atribuir un precio a uno solo.
    flat = []
    for o in offers:
        if _is_type(o, "AggregateOffer") and isinstance(o.get("offers"), list):
            flat.extend(x for x in o["offers"] if isinstance(x, dict))
        else:
            flat.append(o)
    priced = [(o, _price_int(o.get("price"))) for o in flat]
    priced = [(o, p) for o, p in priced if p]
    if not priced:
        rec["notes"].append("Offer sin precio unitario (solo rango o ausente)")
        return rec
    if len({p for _, p in priced}) > 1:
        rec["notes"].append(f"{len(priced)} ofertas con precios distintos; se usa la primera listada")
    offer, price = priced[0]

    rec["price_clp"] = price
    rec["currency"] = offer.get("priceCurrency")
    rec["in_stock"] = AVAILABILITY.get(_tail(offer.get("availability")))
    seller = offer.get("seller")
    rec["seller"] = (seller.get("name") if isinstance(seller, dict) else seller) or None
    if not rec["seller"] and state:
        # El estado embebido mezcla vendedores de otras ofertas y carruseles: solo es pista, nunca el vendedor.
        names = state_sellers(state)
        if names:
            rec["notes"].append(f"vendedor no informado en la oferta; nombres en la página (pista): {sorted(names)[:5]}")
    rec["condition"], how = condition_from(rec["title"] or "", offer.get("itemCondition") or product.get("itemCondition"))
    rec["notes"].append(f"condición: {how}")
    if rec["in_stock"] is None:
        rec["notes"].append(f"disponibilidad no reconocida: {offer.get('availability')!r}")
    rec["price_evidence"] = (f"JSON-LD Offer price={offer.get('price')!r} priceCurrency={offer.get('priceCurrency')!r} "
                             f"availability={_tail(offer.get('availability')) or None} "
                             f"itemCondition={_tail(offer.get('itemCondition')) or None} seller={rec['seller']!r}")
    return rec


SELLER_KEYS = ("sellerName", "sellerDisplayName", "sellerNameDisplay", "soldBy", "vendedor")


def state_sellers(state) -> set[str]:
    return {v.strip() for d in _walk(state) for k, v in d.items()
            if k in SELLER_KEYS and isinstance(v, str) and v.strip()}


def diagnose(html: str) -> dict:
    """Estructura de la página para depurar extracciones fallidas (sin copiar contenido)."""
    tree = LexborHTMLParser(html or "")
    lds, state = _json_scripts(tree)
    types = sorted({str(d.get("@type")) for blob in lds for d in _walk(blob) if "@type" in d})
    price_keys = set()
    if state:
        for d in _walk(state):
            for k, v in d.items():
                if "price" in k.lower() and isinstance(v, (int, float, str, list, dict)):
                    price_keys.add(k)
    ld_urls = [d.get("url") for blob in lds for d in _walk(blob) if _is_type(d, "Product") and d.get("url")]
    model_hrefs = [a.attributes.get("href") for a in tree.css("a[href]")
                   if MODEL_RE.search(a.text() or "") or re.search(r"iphone[\-_]?15", a.attributes.get("href") or "", re.I)]
    ld_model_keys = sorted({k for blob in lds for d in _walk(blob)
                            if _is_type(d, "Product") and MODEL_RE.search(str(d.get("name") or "")) for k in d})
    seller_keys = sorted({k for d in _walk(state) for k in d if "seller" in k.lower()}) if state else []
    return {"jsonld_types": types, "next_data": state is not None, "next_price_keys": sorted(price_keys)[:20],
            "seller_keys": seller_keys[:10], "anchors": len(tree.css("a[href]")),
            "jsonld_product_urls": ld_urls[:5], "model_anchor_hrefs": model_hrefs[:5],
            "jsonld_model_product_keys": ld_model_keys}
