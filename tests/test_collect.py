"""Fixtures sintéticos: no se versiona HTML de las tiendas."""
import json
from datetime import datetime, timezone

from core.verify import verify_offer
from scrapers.retail import product as prod

NOW = datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc)
CAPTURED = "2026-10-24T14:30:00+00:00"


def ld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


def page(*parts):
    return "<html><head>" + "".join(parts) + "</head><body></body></html>"


def offer(**kw):
    base = {"@type": "Offer", "price": "849990", "priceCurrency": "CLP",
            "availability": "https://schema.org/InStock", "seller": {"@type": "Organization", "name": "Digitek"}}
    return {**base, **kw}


def product(name="Iphone 15 Pro 256gb Black Titanium Reacondicionado", offers=None):
    return {"@context": "https://schema.org", "@type": "Product", "name": name, "offers": offers or offer()}


def test_search_links_filter_model_domain_and_max():
    html = """<a href="/iphone-15-pro-256gb-black-titanium-reacondicionado-10216000372001.html">Iphone 15 Pro 256gb</a>
    <a href="/iphone-15-pro-max-256gb-white-10216000372002.html">Iphone 15 Pro Max</a>
    <a href="https://otro.cl/iphone-15-pro-256gb-10216000372003.html">fuera</a>
    <a href="/iphone-15-pro-256gb-black-titanium-reacondicionado-10216000372001.html#reviews">dup</a>
    <a href="/macbook-pro-15-10216000372009.html">Macbook Pro 15</a>"""
    assert prod.product_links(html, "https://www.hites.com/busqueda?q=x", "hites") == [
        "https://www.hites.com/iphone-15-pro-256gb-black-titanium-reacondicionado-10216000372001.html"]


def test_search_links_from_next_data():
    state = {"props": {"pageProps": {"results": [
        {"displayName": "iPhone 15 Pro 256GB Natural Reacondicionado", "url": "https://www.falabella.com/falabella-cl/product/123456/x/123457"},
        {"displayName": "iPhone 15 Pro Max 256GB", "url": "https://www.falabella.com/falabella-cl/product/999999/y/999998"}]}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'
    assert prod.product_links(html, "https://www.falabella.com/falabella-cl/search?Ntt=x", "falabella") == [
        "https://www.falabella.com/falabella-cl/product/123456/x/123457"]


def test_product_refurbished_passes_verify():
    url = "https://www.hites.com/iphone-15-pro-256gb-black-titanium-reacondicionado-10216000372001.html"
    rec = prod.parse_product(page(ld(product())), url, "hites", CAPTURED)
    assert rec["condition"] == "reacondicionado" and rec["price_clp"] == 849990 and rec["seller"] == "Digitek"
    assert verify_offer(rec, NOW) == (True, "verificado en la muestra")


def test_title_beats_schema_new_condition():
    rec = prod.parse_product(page(ld(product(offers=offer(itemCondition="https://schema.org/NewCondition")))),
                             "https://www.hites.com/a-10216000372001.html", "hites", CAPTURED)
    assert rec["condition"] == "reacondicionado"


def test_ambiguous_grade_is_not_a_condition():
    rec = prod.parse_product(page(ld(product(name="Iphone 15 Pro fully Unlocked 256gb grade A",
                                             offers=offer(itemCondition="https://schema.org/NewCondition")))),
                             "https://www.falabella.com/falabella-cl/product/1/x/2", "falabella", CAPTURED)
    assert rec["condition"] is None
    assert verify_offer(rec, NOW)[1] == "condición no confirmada"


def test_out_of_stock_and_missing_price_are_rejected():
    rec = prod.parse_product(page(ld(product(offers=offer(availability="https://schema.org/OutOfStock")))),
                             "https://www.hites.com/a-10216000372001.html", "hites", CAPTURED)
    assert rec["in_stock"] is False and not verify_offer(rec, NOW)[0]
    rec = prod.parse_product(page(ld(product(offers={"@type": "AggregateOffer", "lowPrice": "799990", "highPrice": "899990"}))),
                             "https://www.hites.com/a-10216000372001.html", "hites", CAPTURED)
    assert rec["price_clp"] is None and not verify_offer(rec, NOW)[0]


def test_page_without_jsonld_reports_diagnose():
    rec = prod.parse_product("<html><body>sin datos</body></html>", "https://www.lider.cl/ip/x/1", "lider", CAPTURED)
    assert rec["extraction"] == "ninguna" and rec["price_clp"] is None


def test_price_parsing():
    assert prod._price_int("849.990") == 849990
    assert prod._price_int(849990.0) == 849990
    assert prod._price_int("849990.00") == 849990
    assert prod._price_int(True) is None and prod._price_int("0") is None


def test_links_skip_other_storage_and_dedupe_falabella_sku():
    state = {"results": [
        {"displayName": "Apple iPhone 15 Pro 1TB Blanco Reacondicionado", "url": "https://www.falabella.com/falabella-cl/product/155665968/apple-iphone-15-pro-1tb"},
        {"displayName": "Apple iPhone 15 Pro 128GB", "url": "https://www.falabella.com/falabella-cl/product/127011635/apple-iphone-15-pro-128gb"},
        {"displayName": "iPhone 15 Pro 256GB Reacondicionado", "url": "https://www.falabella.com/falabella-cl/product/111111/iphone-15-pro-256gb"},
        {"displayName": "iPhone 15 Pro 256GB Reacondicionado", "url": "https://www.falabella.com/falabella-cl/product/111111/iphone-15-pro-256gb/111112"},
        {"displayName": "IPHONE 15 PRO 5G 8+256GB REACONDICIONADO", "url": "https://www.falabella.com/falabella-cl/product/222222/iphone-15-pro-8-256gb"}]}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'
    assert prod.product_links(html, "https://www.falabella.com/falabella-cl/search", "falabella") == [
        "https://www.falabella.com/falabella-cl/product/111111/iphone-15-pro-256gb",
        "https://www.falabella.com/falabella-cl/product/222222/iphone-15-pro-8-256gb"]


def test_schema_new_condition_alone_is_not_enough():
    rec = prod.parse_product(page(ld(product(name="Apple iPhone 15 Pro 256GB Titanio Natural",
                                             offers=offer(itemCondition="https://schema.org/NewCondition")))),
                             "https://www.lider.cl/ip/x/00046059090375", "lider", CAPTURED)
    assert rec["condition"] is None
    rec = prod.parse_product(page(ld(product(name="Apple iPhone 15 Pro 256GB Nuevo Sellado"))),
                             "https://www.lider.cl/ip/x/00046059090375", "lider", CAPTURED)
    assert rec["condition"] == "nuevo"


def test_embedded_state_seller_is_only_a_hint():
    state = {"props": {"product": {"sellerName": "Tienda X"}}}
    nd = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(state)}</script>'
    no_seller = offer()
    no_seller.pop("seller")
    rec = prod.parse_product(page(ld(product(offers=no_seller)), nd), "https://www.lider.cl/ip/x/1", "lider", CAPTURED)
    assert rec["seller"] is None and any("pista" in n for n in rec["notes"])
