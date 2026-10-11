from tools import detect
from tools.recon import source_readable, verdict

PRODUCT_HTML = """<html><body><div class="card"><h3>iPhone 15 Pro 256GB Titanio Negro</h3>
<span>$1.099.990</span><s>$1.299.990</s></div>
<div><h3>iPhone 15 Pro Max 256GB</h3><span>$1.299.990</span></div></body></html>"""

JSONLD_HTML = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"iPhone 15 Pro 256GB",
 "offers":{"@type":"Offer","price":"999990","priceCurrency":"CLP"}}</script></head><body></body></html>"""

CF_HTML = "<html><head><title>Just a moment...</title></head><body>cf-chl</body></html>"


def test_samples_skip_max_and_pair_first_price():
    res = detect.analyze_html(PRODUCT_HTML, 200, "https://x.cl/s", "product")
    assert res["samples"] == [{"title": "iPhone 15 Pro 256GB Titanio Negro", "price": 1099990}]
    assert res["has_data"]


def test_jsonld_offer():
    res = detect.analyze_html(JSONLD_HTML, 200, "https://x.cl/p", "product")
    assert res["jsonld_offers"][0]["price"] == "999990"
    assert res["has_data"]


def test_cloudflare_block():
    res = detect.analyze_html(CF_HTML, 403, "https://x.cl", "product")
    assert res["block"] == "cloudflare" and not res["has_data"]


def test_empty_js_shell_has_no_data():
    res = detect.analyze_html('<html><body><div id="root"></div><script>window.__NEXT_DATA__={}</script></body></html>',
                              200, "https://x.cl", "product")
    assert not res["has_data"] and "__NEXT_DATA__" in res["embedded_state"]


def test_promos_detected():
    html = "<body>" + " ".join(f"<p>{n}% dcto con tarjeta</p>" for n in (10, 20, 30, 40)) + "</body>"
    assert detect.analyze_html(html, 200, "https://x.cl", "promos")["has_data"]


def test_api_ml_results():
    body = '{"results":[{"title":"Apple iPhone 15 Pro (256 GB)","price":899990,"condition":"new","seller":{"id":1}}]}'
    res = detect.analyze_api(body, 200, "mercadolibre")
    assert res["has_data"] and res["samples"][0]["price"] == 899990


def test_api_forbidden_is_login():
    res = detect.analyze_api('{"message":"forbidden"}', 403, "mercadolibre")
    assert not res["has_data"] and res["login"]


def test_verdict_and_readable():
    ok = {"probe": "product", "static": {"has_data": False}, "browser": {"has_data": True}}
    assert verdict(ok, "product")[0] == "ok_js"
    blk = {"probe": "promos", "static": {"has_data": False, "block": "cloudflare"}}
    assert verdict(blk, "promos")[0] == "bloqueado"
    probes = [{"probe": "product", "verdict": "ok_js", "cause": "js"}, {"probe": "promos", "verdict": "bloqueado", "cause": "waf"}]
    assert source_readable({"kind": "retail"}, probes)[0] == "partial"
    assert source_readable({"kind": "banco"}, [{"probe": "promos", "verdict": "login", "cause": "x"}])[0] == "blocked"


def test_404_with_prices_is_not_data():
    res = detect.analyze_html(PRODUCT_HTML, 404, "https://x.cl/s", "product")
    assert res["not_found"] and not res["has_data"]
    assert verdict({"static": res}, "product")[0] == "url_invalida"


def test_waf_script_on_healthy_page_is_not_block():
    html = "<html><head><script>window._pxAppId='x'</script></head><body>" + "contenido " * 200 + PRODUCT_HTML + "</body></html>"
    res = detect.analyze_html(html, 200, "https://x.cl/s", "product")
    assert res["waf"] == "perimeterx" and res["block"] is None and res["has_data"]


def test_account_verification_redirect_is_login():
    res = detect.analyze_html("<html><body>Verifica</body></html>", 200,
                              "https://www.mercadolibre.cl/gz/account-verification?go=x", "product")
    assert res["login"] and verdict({"static": res}, "product")[0] == "login"


def test_generic_prices_without_sample():
    html = "<body>" + " ".join(f"<p>Notebook {i} $1.{i}00.990</p>" for i in range(1, 6)) + "</body>"
    res = detect.analyze_html(html, 200, "https://x.cl", "product")
    assert not res["has_data"] and res["generic_prices"]
    assert verdict({"static": res}, "product")[0] == "precios_sin_muestra"


def test_discover_search_form_and_promo_links():
    from tools.recon import discover
    home = """<form action="/busqueda"><input type="search" name="q"></form>
    <a href="/beneficios/tarjeta">Beneficios</a><a href="https://otro.com/oferta">x</a>"""
    assert discover(home, "https://www.tienda.cl", "product", "iphone 15") == ["https://www.tienda.cl/busqueda?q=iphone+15"]
    assert discover(home, "https://www.tienda.cl", "promos", "") == ["https://www.tienda.cl/beneficios/tarjeta"]
