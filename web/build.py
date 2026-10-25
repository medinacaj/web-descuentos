"""Genera el sitio estático Ahorro Real desde los datos del sistema (no se escriben precios a mano).

  python web/build.py                       # prototipo: noindex + robots bloqueado, en site/dist
  python web/build.py --modo publico       # producción: indexable, sitemap.xml (exige SITE_BASE_URL)
  python web/build.py --preview            # vista previa con enlaces relativos a archivos (Artifact)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
NOMBRE = "Ahorro Real"  # nombre provisional; no verificado como marca ni dominio
PLACEHOLDER_URL = "https://ahorroreal.example"

e = html.escape


def clp(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


def fecha(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d.strftime("%d-%m-%Y")


# ----------------------------------------------------------------------------- estilos
CSS = """
/* Diseño: boleta de compra. Cada precio se lee como un desglose, no como un cartel de oferta. */
:root{
  --bg:#f3f6f4; --surface:#ffffff; --fg:#13201b; --muted:#53635c; --line:#d5ddd8;
  --accent:#0d6e53; --accent-ink:#ffffff; --warn:#8a5a00; --warn-bg:#fdf1d8; --bad:#a1262d; --bad-bg:#fbe4e5;
  --ok-bg:#dff1ea;
  --f-display:"Archivo",system-ui,sans-serif; --f-body:"Public Sans",system-ui,sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0d1412; --surface:#15201c; --fg:#e3ebe7; --muted:#9db0a8; --line:#2a3833;
  --accent:#4cc9a0; --accent-ink:#06261c; --warn:#f2c46b; --warn-bg:#33270f; --bad:#ff8f95; --bad-bg:#3a1a1d;
  --ok-bg:#12352a; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0d1412; --surface:#15201c; --fg:#e3ebe7; --muted:#9db0a8; --line:#2a3833;
  --accent:#4cc9a0; --accent-ink:#06261c; --warn:#f2c46b; --warn-bg:#33270f; --bad:#ff8f95; --bad-bg:#3a1a1d;
  --ok-bg:#12352a; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:400 1rem/1.6 var(--f-body)}
a{color:var(--accent)} a:focus-visible,button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.wrap{max-width:68rem;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.aviso{background:var(--warn-bg);color:var(--warn);font-size:.875rem}
.aviso .wrap{padding-block:.5rem}
header.top .wrap{display:flex;flex-wrap:wrap;gap:.75rem 2rem;align-items:center;justify-content:space-between;padding-block:1rem}
.marca{font:800 1.35rem/1 var(--f-display);font-stretch:125%;letter-spacing:-.01em;color:var(--fg);text-decoration:none}
.marca span{color:var(--accent)}
nav ul{display:flex;flex-wrap:wrap;gap:1.25rem;list-style:none;margin:0;padding:0}
nav a{color:var(--muted);text-decoration:none;font-weight:600} nav a[aria-current]{color:var(--fg);text-decoration:underline;text-underline-offset:.3em}
main .wrap{display:grid;gap:3rem;padding-block:2rem 4rem}
h1,h2,h3{font-family:var(--f-display);font-stretch:112%;line-height:1.15;text-wrap:balance;margin:0}
h1{font-size:clamp(2rem,5vw,3.25rem);font-weight:800;letter-spacing:-.02em}
h2{font-size:1.5rem;font-weight:700} h3{font-size:1.1rem;font-weight:700}
p{margin:0;max-width:65ch} .lead{font-size:1.15rem;color:var(--muted)}
.stack{display:grid;gap:1rem} .stack-sm{display:grid;gap:.5rem}
.eyebrow{font:600 .75rem/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.hero{display:grid;gap:2rem;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);align-items:start}
@media (max-width:760px){.hero{grid-template-columns:minmax(0,1fr)}}
.boleta{background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:1.25rem 1.25rem 1rem;font-family:var(--f-mono);font-size:.9rem;
  box-shadow:0 1px 0 var(--line);position:relative}
.boleta::after{content:"";position:absolute;left:0;right:0;bottom:-8px;height:8px;
  background:linear-gradient(-45deg,transparent 6px,var(--surface) 0) 0 0/12px 8px repeat-x,linear-gradient(45deg,transparent 6px,var(--surface) 0) 0 0/12px 8px repeat-x}
.boleta h3{font-family:var(--f-mono);font-size:.8rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-stretch:100%}
.boleta dl{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.35rem 1rem;margin:.75rem 0 0}
.boleta dt{color:var(--muted)} .boleta dd{margin:0;text-align:right;font-variant-numeric:tabular-nums}
.boleta .total{border-top:1px dashed var(--line);padding-top:.5rem;font-weight:700;color:var(--fg)}
.boleta .nota{margin-top:.75rem;color:var(--muted);font-size:.8rem}
.pill{display:inline-block;font:600 .75rem/1 var(--f-mono);letter-spacing:.04em;padding:.35rem .55rem;border-radius:999px;white-space:nowrap}
.ok{background:var(--ok-bg);color:var(--accent)} .warn{background:var(--warn-bg);color:var(--warn)} .bad{background:var(--bad-bg);color:var(--bad)}
.pasos{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:1.5rem;list-style:none;padding:0;margin:0;counter-reset:p}
.pasos li{counter-increment:p;display:grid;align-content:start;gap:.4rem;border-top:2px solid var(--fg);padding-top:.75rem}
.pasos li::before{content:"Paso " counter(p);font:600 .75rem/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.tabla{overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{padding:.65rem .8rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font:600 .75rem/1.2 var(--f-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
tr:last-child td{border-bottom:0} .sub{color:var(--muted);font-size:.85rem;margin-top:.2rem} td.num{text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.destacado{display:grid;gap:1rem;grid-template-columns:minmax(0,1fr) auto;align-items:end;padding-block:1.5rem;border-block:1px solid var(--line)}
@media (max-width:600px){.destacado{grid-template-columns:minmax(0,1fr)}}
.precio-grande{font:700 clamp(2rem,4vw,2.75rem)/1 var(--f-mono);font-variant-numeric:tabular-nums}
.boton{display:inline-block;background:var(--accent);color:var(--accent-ink);font-weight:700;text-decoration:none;padding:.7rem 1.1rem;border-radius:4px}
.veredicto{display:grid;gap:.5rem;padding:1rem 1.25rem;border-left:4px solid var(--warn);background:var(--warn-bg);color:var(--fg)}
.veredicto strong{font-family:var(--f-display);font-stretch:112%;font-size:1.1rem;color:var(--warn)}
ul.motivos{margin:0;padding-left:1.1rem;display:grid;gap:.25rem}
.migas{font-size:.875rem;color:var(--muted)} .migas ol{display:flex;flex-wrap:wrap;gap:.4rem;list-style:none;margin:0;padding:0}
.migas li+li::before{content:"/";margin-right:.4rem;color:var(--line)}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.875rem}
footer .wrap{display:grid;gap:.75rem;padding-block:2rem}
@media (prefers-reduced-motion:no-preference){a{transition:color .15s}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@100..125,600..800'
         '&family=IBM+Plex+Mono:wght@400;600;700&family=Public+Sans:wght@400;600;700&display=swap">')


# ----------------------------------------------------------------------------- sitio
class Site:
    def __init__(self, modo: str, preview: bool, base_url: str):
        self.modo, self.preview, self.base = modo, preview, base_url.rstrip("/")
        self.indexable = modo == "publico"
        self.pages: list[dict] = []

    def href(self, desde: str, hacia: str) -> str:
        """Producción: rutas limpias absolutas. Vista previa: rutas relativas a index.html."""
        if not self.preview:
            return hacia
        desde = "/" if desde == "/404" else desde
        rel = posixpath.relpath(hacia.strip("/") or ".", desde.strip("/") or ".")
        return ("" if rel == "." else rel + "/") + "index.html"

    def add(self, path, title, description, body, crumbs=None, jsonld=None):
        self.pages.append(dict(path=path, title=title, description=description, body=body,
                               crumbs=crumbs or [], jsonld=jsonld or []))

    def nav(self, path):
        items = [("/", "Inicio"), ("/ofertas/iphone-15-pro-256gb/", "Seguimiento"), ("/como-funciona/", "Cómo funciona"),
                 ("/fuentes/", "Fuentes")]
        lis = "".join(f'<li><a href="{self.href(path, p)}"{" aria-current=\"page\"" if p == path else ""}>{e(t)}</a></li>'
                      for p, t in items)
        return f'<nav aria-label="Principal"><ul>{lis}</ul></nav>'

    def render(self, pg: dict, full: bool) -> str:
        path, url = pg["path"], self.base + pg["path"]
        robots = "index, follow" if self.indexable else "noindex, nofollow"
        ld = list(pg["jsonld"])
        if pg["crumbs"]:
            ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": self.base + p} for i, (p, n) in enumerate(pg["crumbs"])]})
        head = (f'<title>{e(pg["title"])}</title>'
                '<meta name="claude:viewport-fit-sides" content="cover">'
                f'<meta name="description" content="{e(pg["description"])}">'
                f'<meta name="robots" content="{robots}">'
                f'<link rel="canonical" href="{e(url)}">'
                f'<meta property="og:type" content="website"><meta property="og:site_name" content="{NOMBRE}">'
                f'<meta property="og:title" content="{e(pg["title"])}"><meta property="og:description" content="{e(pg["description"])}">'
                f'<meta property="og:url" content="{e(url)}"><meta property="og:locale" content="es_CL">'
                '<meta name="twitter:card" content="summary">'
                + FONTS + f"<style>{CSS}</style>"
                + "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld))
        aviso = ('<div class="aviso" role="note"><div class="wrap">Prototipo. Los precios son una muestra del '
                 f'{e(self.comprobado)} y no son ofertas vigentes. Comprueba siempre en la tienda.</div></div>'
                 if not self.indexable else "")
        crumbs = ""
        if pg["crumbs"]:
            lis = "".join(f'<li><a href="{self.href(path, p)}">{e(n)}</a></li>' if p != path else f'<li aria-current="page">{e(n)}</li>'
                          for p, n in pg["crumbs"])
            crumbs = f'<nav class="migas" aria-label="Ruta"><ol>{lis}</ol></nav>'
        body = (f'{aviso}<header class="top"><div class="wrap"><a class="marca" href="{self.href(path, "/")}">Ahorro<span>Real</span></a>'
                f'{self.nav(path)}</div></header>'
                f'<main><div class="wrap">{crumbs}{pg["body"]}</div></main>'
                f'<footer><div class="wrap"><p>{NOMBRE} compara precios publicados por tiendas chilenas y no vende productos. '
                'No usa enlaces de afiliado ni recibe pago de las tiendas. Precio, stock y condiciones pueden cambiar: '
                'la tienda manda.</p><p>Generado el ' + e(self.generado) + '.</p></div></footer>')
        if not full:  # el Artifact agrega su propio esqueleto a la página principal
            return head + body
        return (f'<!doctype html><html lang="es-CL"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">{head}</head>'
                f'<body>{body}</body></html>')

    def write(self, out: Path) -> None:
        if out.exists():
            shutil.rmtree(out)
        for pg in self.pages:
            dest = out / pg["path"].strip("/") / "index.html" if pg["path"] != "/404" else out / "404.html"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(self.render(pg, full=not (self.preview and pg["path"] == "/")), encoding="utf8")
        if self.indexable:
            urls = "".join(f"<url><loc>{e(self.base + p['path'])}</loc></url>" for p in self.pages if p["path"] != "/404")
            (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>'
                                             f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
            (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {self.base}/sitemap.xml\n")
        else:
            (out / "robots.txt").write_text("# Prototipo: no indexar hasta publicar con datos vigentes.\nUser-agent: *\nDisallow: /\n")


# ----------------------------------------------------------------------------- contenido
def veredicto(oferta: dict, dias_historial: int) -> tuple[str, list[str]]:
    """Reglas del proyecto: con confianza baja nunca hay recomendación principal."""
    motivos = []
    if not oferta.get("vendedor"):
        motivos.append("La tienda no informa el vendedor en la oferta (es un marketplace).")
    motivos.append("Despacho y cargos no verificados: el precio final pagadero puede ser mayor.")
    if dias_historial < 14:
        motivos.append("Sin historial suficiente: la referencia real necesita 2 a 3 semanas de precios.")
    return ("COMPARAR UN POCO MÁS" if motivos else "BUENA OFERTA"), motivos


def build(site: Site, data: dict, recon: dict) -> None:
    prod = data["productos"][0]
    ofertas = sorted(prod["ofertas"], key=lambda o: o["precio"])
    mejor = ofertas[0]
    site.comprobado = fecha(data["comprobado"])
    site.generado = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    P = f'/ofertas/{prod["slug"]}/'
    legibles = sum(1 for t in prod["estado_tiendas"] if t["estado"] == "legible")

    # Inicio --------------------------------------------------------------------------------
    pasos = [("Recolectar", "Leemos la ficha de cada producto en la tienda, respetando sus reglas de acceso y sin forzar bloqueos."),
             ("Verificar", "Solo pasa lo que trae capacidad, condición, precio en pesos y stock explícitos. Lo dudoso se descarta."),
             ("Comparar", "Contra el historial del mismo producto y contra otras tiendas. El precio tachado no cuenta."),
             ("Avisar", "Solo cuando el ahorro es real y verificable. Si no hay nada que valga la pena, no publicamos nada.")]
    site.add("/", f"{NOMBRE} · Ahorro real en compras en Chile",
             "Comparamos el precio final que pagas en tiendas chilenas contra lo que el mismo producto ha costado de verdad. "
             "Sin precio tachado ni ofertas infladas.",
             f'''<section class="hero">
  <div class="stack"><p class="eyebrow">Compras en Chile</p><h1>Ahorro real, no precio tachado.</h1>
  <p class="lead">Medimos cuánto pagas de verdad: precio de la ficha, descuentos confirmados y despacho, comparado con lo que el mismo producto ha costado antes y en otras tiendas.</p></div>
  <div class="boleta" aria-label="Ejemplo de desglose"><h3>Así leemos un precio</h3><dl>
  <dt>Precio en la ficha</dt><dd>{clp(mejor["precio"])}</dd>
  <dt>Descuentos inmediatos</dt><dd>sin confirmar</dd>
  <dt>Cupones confirmados</dt><dd>ninguno</dd>
  <dt>Despacho y cargos</dt><dd>sin verificar</dd>
  <dt class="total">Precio final pagadero</dt><dd class="total">desde {clp(mejor["precio"])}</dd></dl>
  <p class="nota">{e(prod["nombre"])} reacondicionado, {e(mejor["tienda"])}, muestra del {site.comprobado}.</p></div>
</section>
<section class="stack" aria-labelledby="seg"><p class="eyebrow">Seguimiento activo</p>
  <div class="destacado"><div class="stack-sm"><h2 id="seg">{e(prod["nombre"])}</h2>
  <p>{len(ofertas)} fichas reacondicionadas verificadas en {legibles} de {len(prod["estado_tiendas"])} tiendas. {e(prod["regla_variante"])}</p></div>
  <div class="stack-sm"><span class="eyebrow">Desde</span><span class="precio-grande">{clp(mejor["precio"])}</span>
  <a class="boton" href="{site.href("/", P)}">Ver el seguimiento</a></div></div>
</section>
<section class="stack" aria-labelledby="como"><h2 id="como">Cómo decidimos</h2><ol class="pasos">
  {"".join(f"<li><h3>{e(t)}</h3><p>{e(d)}</p></li>" for t, d in pasos)}</ol>
  <p><a href="{site.href("/", "/como-funciona/")}">Lee las reglas completas</a></p></section>''',
             jsonld=[{"@context": "https://schema.org", "@type": "WebSite", "name": NOMBRE, "url": site.base + "/", "inLanguage": "es-CL"}])

    # Seguimiento del producto ----------------------------------------------------------------
    v, motivos = veredicto(mejor, dias_historial=0)
    filas = "".join(f'<tr><td class="num">{clp(o["precio"])}</td><td>{e(o["titulo"])}<div class="sub">{e(o["tienda"])} · '
                    f'vendedor {e(o["vendedor"] or "no informado")}</div></td>'
                    f'<td><a href="{e(o["url"])}" rel="nofollow noopener" target="_blank">Ver ficha</a></td></tr>'
                    for o in ofertas)
    estado_cls = {"legible": "ok", "bloqueada": "bad", "pendiente": "warn"}
    tiendas = "".join(f'<tr><td>{e(t["tienda"])}</td><td><span class="pill {estado_cls[t["estado"]]}">{e(t["estado"])}</span></td><td>{e(t["detalle"])}</td></tr>'
                      for t in prod["estado_tiendas"])
    desc = "".join(f'<li>{e(d["motivo"])}{f" ({d['cantidad']})" if d["cantidad"] else ""} · {e(d["tienda"])}</li>' for d in prod["descartadas"])
    site.add(P, f'{prod["nombre"]}: precios verificados en Chile · {NOMBRE}',
             f'Seguimiento del {prod["nombre"]} en tiendas chilenas: precio de ficha verificado por condición '
             f'(nuevo, reacondicionado, seminuevo), vendedor, ofertas descartadas y por qué.',
             f'''<section class="hero"><div class="stack"><p class="eyebrow">{e(prod["categoria"])} · {e(prod["marca"])}</p>
  <h1>{e(prod["nombre"])}</h1><p class="lead">{e(prod["regla_variante"])} Nuevo, reacondicionado y seminuevo se comparan por separado.</p>
  <div class="veredicto" role="status"><strong>{v}</strong><ul class="motivos">{"".join(f"<li>{e(m)}</li>" for m in motivos)}</ul></div></div>
  <div class="boleta"><h3>Mejor precio reacondicionado</h3><dl>
  <dt>Tienda</dt><dd>{e(mejor["tienda"])}</dd><dt>Vendedor</dt><dd>{e(mejor["vendedor"] or "no informado")}</dd>
  <dt>Precio en la ficha</dt><dd>{clp(mejor["precio"])}</dd><dt>Despacho</dt><dd>sin verificar</dd>
  <dt>Referencia real</dt><dd>sin historial</dd>
  <dt class="total">Ahorro real</dt><dd class="total">no calculable</dd></dl>
  <p class="nota">Comprobado el {site.comprobado}. Sin historial no se puede decir si este precio es bajo.</p></div></section>
<section class="stack" aria-labelledby="reac"><h2 id="reac">Reacondicionado</h2>
  <div class="tabla"><table><thead><tr><th scope="col">Precio</th><th scope="col">Producto en la ficha</th><th scope="col">Enlace</th></tr></thead><tbody>{filas}</tbody></table></div></section>
<section class="stack" aria-labelledby="nuevo"><h2 id="nuevo">Nuevo y seminuevo</h2>
  <p>Sin ofertas verificadas. Apple dejó de vender este modelo nuevo en 2024, y las fichas que se marcaban como nuevas no lo decían en el título, así que se descartaron.</p></section>
<section class="stack" aria-labelledby="desc"><h2 id="desc">Descartadas y por qué</h2><ul class="motivos">{desc}</ul></section>
<section class="stack" aria-labelledby="tiendas"><h2 id="tiendas">Tiendas revisadas</h2>
  <div class="tabla"><table><thead><tr><th scope="col">Tienda</th><th scope="col">Estado</th><th scope="col">Detalle</th></tr></thead><tbody>{tiendas}</tbody></table></div>
  <p><a href="{site.href(P, "/fuentes/")}">Ver todas las fuentes</a></p></section>''',
             crumbs=[("/", "Inicio"), (P, prod["nombre"])])

    # Cómo funciona -----------------------------------------------------------------------------
    reglas = [("Precio final pagadero", "Precio de la ficha, menos descuentos inmediatos y cupones confirmados, más despacho, comisiones y cargos obligatorios."),
              ("Referencia real", "Sale del historial del mismo producto (mediana de 60 días) y del precio en otras tiendas, nunca del precio normal publicado."),
              ("Variante bloqueada", "Se compara la misma capacidad y condición. Un 128 GB nunca se compara contra un 256 GB."),
              ("Plataforma no es vendedor", "En marketplaces se muestra quién vende. Si la tienda no lo informa, lo decimos."),
              ("Cupones y beneficios", "Solo cuentan los confirmados en la fuente oficial. Un código visto en un foro es una pista, no un descuento."),
              ("Cashback y puntos", "Se muestran aparte: lo que pagas hoy, lo que vuelve después y el costo neto.")]
    clases = [("Sobresaliente", "20% o más bajo la referencia real"), ("Buena", "entre 10% y 19,9%"), ("Descuento menor", "entre 1% y 9,9%"),
              ("Sin ahorro real", "igual o sobre el mercado"), ("Dudosa", "referencia inflada, condiciones poco claras o información insuficiente")]
    site.add("/como-funciona/", f"Cómo calculamos el ahorro real · {NOMBRE}",
             "Reglas de verificación de Ahorro Real: precio final pagadero, referencia real, variantes bloqueadas, "
             "cupones confirmados y clasificación de ofertas.",
             f'''<section class="stack"><p class="eyebrow">Método</p><h1>Cómo calculamos el ahorro real</h1>
  <p class="lead">No buscamos el descuento más llamativo, sino la compra más conveniente, verificable y segura.</p></section>
<section class="stack" aria-labelledby="reg"><h2 id="reg">Reglas</h2><div class="tabla"><table><tbody>
  {"".join(f'<tr><th scope="row">{e(t)}</th><td>{e(d)}</td></tr>' for t, d in reglas)}</tbody></table></div></section>
<section class="stack" aria-labelledby="cla"><h2 id="cla">Clasificación</h2><div class="tabla"><table><tbody>
  {"".join(f'<tr><th scope="row">{e(t)}</th><td>{e(d)}</td></tr>' for t, d in clases)}</tbody></table></div>
  <p>La confianza es baja cuando falta evidencia, y una oferta con confianza baja nunca es la recomendación principal.</p></section>''',
             crumbs=[("/", "Inicio"), ("/como-funciona/", "Cómo funciona")])

    # Fuentes ----------------------------------------------------------------------------------
    tipo = {"retail": "Tienda", "banco": "Banco", "billetera": "Billetera", "caja": "Caja de compensación",
            "operador": "Operador", "comparador": "Comparador"}
    leg = {"ok": ("legible", "ok"), "partial": ("parcial", "warn"), "blocked": ("no legible", "bad"), "unknown": ("sin probar", "warn")}
    filas_f = "".join(f'<tr><td>{e(s["name"])}</td><td>{e(tipo.get(s["kind"], s["kind"]))}</td>'
                      f'<td><span class="pill {leg[s["readable"]][1]}">{leg[s["readable"]][0]}</span></td></tr>' for s in recon["sources"])
    n = len(recon["sources"])
    nok = sum(s["readable"] == "ok" for s in recon["sources"])
    site.add("/fuentes/", f"Fuentes revisadas en Chile · {NOMBRE}",
             f"Las {n} tiendas, bancos, billeteras, operadores y comparadores chilenos que revisa Ahorro Real y cuáles se pueden leer.",
             f'''<section class="stack"><p class="eyebrow">Transparencia</p><h1>Fuentes revisadas</h1>
  <p class="lead">Revisamos {n} fuentes; {nok} se leen completas. Las que bloquean el acceso automático quedan fuera: no intentamos saltarnos esos bloqueos.</p>
  <p>Mapa del {fecha(recon["checked_at"])}. "Legible" se refiere a la página de búsqueda o de beneficios; la ficha de producto puede comportarse distinto (ver el seguimiento).</p></section>
<div class="tabla"><table><thead><tr><th scope="col">Fuente</th><th scope="col">Tipo</th><th scope="col">Lectura</th></tr></thead><tbody>{filas_f}</tbody></table></div>''',
             crumbs=[("/", "Inicio"), ("/fuentes/", "Fuentes")])

    site.add("/404", f"Página no encontrada · {NOMBRE}", "La página que buscas no existe.",
             f'<section class="stack"><h1>Esta página no existe</h1><p><a href="{site.href("/404", "/")}">Volver al inicio</a></p></section>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["prototipo", "publico"], default="prototipo")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    base = os.environ.get("SITE_BASE_URL", PLACEHOLDER_URL)
    if a.modo == "publico" and base == PLACEHOLDER_URL:
        ap.error("--modo publico exige SITE_BASE_URL con el dominio definitivo")
    data = json.loads((ROOT / "data" / "ofertas.json").read_text(encoding="utf8"))
    recon = json.loads(sorted((REPO / "reports").glob("recon_*.json"))[-1].read_text(encoding="utf8"))
    site = Site(a.modo, a.preview, base)
    build(site, data, recon)
    out = Path(a.out) if a.out else ROOT / ("preview" if a.preview else "dist")
    site.write(out)
    print(f"{len(site.pages)} páginas en {out} · modo {a.modo}{' · preview' if a.preview else ''}")


if __name__ == "__main__":
    main()
