"""Genera el sitio estático desde los datos del sistema. No se escriben precios ni beneficios a mano.

  python web/build.py                       # prototipo: noindex + robots bloqueado, en web/dist
  python web/build.py --modo publico        # producción: indexable + sitemap.xml (exige SITE_BASE_URL)
  python web/build.py --preview             # vista previa con enlaces relativos a archivos (Artifact)

Datos: web/data/ofertas.json (recolector de fichas), web/data/beneficios.json (recolector de beneficios,
opcional: sin él la portada muestra un estado vacío honesto) y el último reports/recon_*.json.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import shutil
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
NOMBRE = "Ahorro Real"  # nombre provisional; no verificado como marca ni dominio
PLACEHOLDER_URL = "https://ahorroreal.example"
TZ = ZoneInfo("America/Santiago")
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_PLURAL = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]
DIAS_CORTOS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]

e = html.escape


def clp(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


def fecha(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y")


# ----------------------------------------------------------------------------- estilos
CSS = """
/* Layout: columna editorial; la semana (Lu–Do) es la columna vertebral porque los beneficios en Chile se anuncian por día. */
:root{
  --bg:#f3f4f8; --surface:#ffffff; --fg:#141827; --muted:#586078; --line:#dadde8;
  --accent:#2347d9; --accent-ink:#ffffff; --mark:#ffd84a; --mark-ink:#141827;
  --ok:#0b6b4f; --ok-bg:#dcf2e8; --warn:#8a5a00; --warn-bg:#fdf0d2; --bad:#a3262e; --bad-bg:#fbe3e4;
  --f-display:"Schibsted Grotesk",system-ui,sans-serif; --f-body:"Instrument Sans",system-ui,sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f1220; --surface:#171b2e; --fg:#e6e8f2; --muted:#9aa1bd; --line:#2a3050;
  --accent:#8ea6ff; --accent-ink:#0f1220; --mark:#ffd84a; --mark-ink:#141827;
  --ok:#5fd3a6; --ok-bg:#12332a; --warn:#f2c46b; --warn-bg:#33270f; --bad:#ff8f95; --bad-bg:#3a1a1d; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f1220; --surface:#171b2e; --fg:#e6e8f2; --muted:#9aa1bd; --line:#2a3050;
  --accent:#8ea6ff; --accent-ink:#0f1220; --mark:#ffd84a; --mark-ink:#141827;
  --ok:#5fd3a6; --ok-bg:#12332a; --warn:#f2c46b; --warn-bg:#33270f; --bad:#ff8f95; --bad-bg:#3a1a1d; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:400 1rem/1.6 var(--f-body)}
a{color:var(--accent);text-underline-offset:.2em} a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.wrap{max-width:70rem;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.aviso{background:var(--fg);color:var(--bg);font-size:.85rem} .aviso .wrap{padding-block:.45rem}
header.top .wrap{display:flex;flex-wrap:wrap;gap:.75rem 2rem;align-items:baseline;justify-content:space-between;padding-block:1.1rem}
.marca{font:900 1.3rem/1 var(--f-display);letter-spacing:-.02em;color:var(--fg);text-decoration:none}
.marca mark{background:var(--mark);color:var(--mark-ink);padding:0 .2em;border-radius:2px}
nav ul{display:flex;flex-wrap:wrap;gap:1.25rem;list-style:none;margin:0;padding:0}
nav a{color:var(--muted);text-decoration:none;font-weight:600} nav a[aria-current]{color:var(--fg);box-shadow:inset 0 -3px 0 var(--mark)}
main .wrap{display:grid;gap:3.5rem;padding-block:1.5rem 4rem}
h1,h2,h3{font-family:var(--f-display);line-height:1.08;text-wrap:balance;margin:0}
h1{font-size:clamp(2.2rem,6vw,4rem);font-weight:900;letter-spacing:-.03em}
h2{font-size:clamp(1.4rem,3vw,1.9rem);font-weight:800;letter-spacing:-.015em} h3{font-size:1.05rem;font-weight:700}
h1 mark{background:linear-gradient(transparent 58%,var(--mark) 58%,var(--mark) 92%,transparent 92%);color:inherit}
p{margin:0;max-width:65ch} .lead{font-size:1.15rem;color:var(--muted)}
.stack{display:grid;gap:1rem} .stack-sm{display:grid;gap:.45rem}
.eyebrow{font:600 .72rem/1 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.semana{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.4rem;list-style:none;margin:0;padding:0}
.semana a{display:grid;gap:.15rem;justify-items:center;padding:.7rem .2rem;border:1px solid var(--line);border-radius:6px;
  background:var(--surface);color:var(--fg);text-decoration:none}
.semana .d{font:700 .8rem/1 var(--f-mono);letter-spacing:.05em;color:var(--muted)}
.semana .n{font:800 1.5rem/1 var(--f-display);font-variant-numeric:tabular-nums}
.semana .l{font-size:.7rem;color:var(--muted)}
.semana .hoy a{background:var(--mark);border-color:var(--mark);color:var(--mark-ink)} .semana .hoy .d,.semana .hoy .l{color:var(--mark-ink)}
.lista{display:grid;gap:0;border-top:2px solid var(--fg)}
.fila{display:grid;grid-template-columns:5.5rem minmax(0,1fr) auto;gap:.25rem 1rem;align-items:baseline;padding:.9rem 0;border-bottom:1px solid var(--line)}
.pct{font:800 2rem/1 var(--f-display);font-variant-numeric:tabular-nums;color:var(--accent)}
.comercio{font-weight:700} .meta{grid-column:2/-1;color:var(--muted);font-size:.9rem}
.emisor{font:600 .75rem/1 var(--f-mono);letter-spacing:.04em;padding:.35rem .5rem;border:1px solid var(--line);border-radius:4px;white-space:nowrap}
@media (max-width:560px){.fila{grid-template-columns:4.2rem minmax(0,1fr)} .fila .emisor{grid-column:2;justify-self:start} .pct{font-size:1.6rem}}
.vacio{padding:1.25rem;border:1px dashed var(--line);border-radius:6px;color:var(--muted)}
.pill{display:inline-block;font:600 .72rem/1 var(--f-mono);letter-spacing:.04em;padding:.35rem .55rem;border-radius:999px;white-space:nowrap}
.ok{background:var(--ok-bg);color:var(--ok)} .warn{background:var(--warn-bg);color:var(--warn)} .bad{background:var(--bad-bg);color:var(--bad)}
.duo{display:grid;gap:2rem;grid-template-columns:minmax(0,1fr) minmax(0,1fr)} @media (max-width:760px){.duo{grid-template-columns:minmax(0,1fr)}}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:1.25rem;display:grid;gap:.75rem;align-content:start}
.precio{font:800 clamp(2rem,4vw,2.6rem)/1 var(--f-display);font-variant-numeric:tabular-nums}
dl.kv{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.35rem 1rem;margin:0;font-size:.95rem}
dl.kv dt{color:var(--muted)} dl.kv dd{margin:0;text-align:right;font-family:var(--f-mono);font-size:.85rem;font-variant-numeric:tabular-nums}
.boton{display:inline-block;justify-self:start;background:var(--accent);color:var(--accent-ink);font-weight:700;text-decoration:none;padding:.65rem 1rem;border-radius:6px}
.veredicto{display:grid;gap:.5rem;padding:1rem 1.25rem;border-left:4px solid var(--warn);background:var(--warn-bg)}
.veredicto strong{font-family:var(--f-display);font-weight:800;color:var(--warn)}
ul.motivos{margin:0;padding-left:1.1rem;display:grid;gap:.25rem}
.tabla{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{padding:.65rem .8rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{font:600 .72rem/1.2 var(--f-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
tr:last-child td{border-bottom:0} td.num{text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.sub{color:var(--muted);font-size:.85rem;margin-top:.2rem}
.pasos{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:1.5rem;list-style:none;padding:0;margin:0;counter-reset:p}
.pasos li{counter-increment:p;display:grid;align-content:start;gap:.4rem;padding-top:.75rem;border-top:1px solid var(--line)}
.pasos li::before{content:counter(p);font:800 1.6rem/1 var(--f-display);color:var(--accent)}
.migas{font-size:.875rem;color:var(--muted)} .migas ol{display:flex;flex-wrap:wrap;gap:.4rem;list-style:none;margin:0;padding:0}
.migas li+li::before{content:"/";margin-right:.4rem;color:var(--line)}
section[id]{scroll-margin-top:1rem}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.875rem} footer .wrap{display:grid;gap:.75rem;padding-block:2rem}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@600;700;800;900'
         '&family=Instrument+Sans:wght@400;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap">')


# ----------------------------------------------------------------------------- sitio
class Site:
    def __init__(self, modo: str, preview: bool, base_url: str, hoy: date):
        self.modo, self.preview, self.base, self.hoy = modo, preview, base_url.rstrip("/"), hoy
        self.indexable = modo == "publico"
        self.pages: list[dict] = []
        self.aviso_txt = ""

    def href(self, desde: str, hacia: str) -> str:
        """Producción: rutas limpias absolutas. Vista previa: rutas relativas a index.html (con #ancla opcional)."""
        hacia, _, ancla = hacia.partition("#")
        ancla = f"#{ancla}" if ancla else ""
        if not self.preview:
            return hacia + ancla
        desde = "/" if desde == "/404" else desde
        rel = posixpath.relpath(hacia.strip("/") or ".", desde.strip("/") or ".")
        return ("" if rel == "." else rel + "/") + "index.html" + ancla

    def add(self, path, title, description, body, crumbs=None, jsonld=None):
        self.pages.append(dict(path=path, title=title, description=description, body=body,
                               crumbs=crumbs or [], jsonld=jsonld or []))

    def nav(self, path):
        items = [("/", "Hoy"), ("/beneficios/", "Beneficios"), ("/ofertas/iphone-15-pro-256gb/", "Precios"),
                 ("/como-funciona/", "Cómo funciona"), ("/fuentes/", "Fuentes")]
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
        aviso = (f'<div class="aviso" role="note"><div class="wrap">{e(self.aviso_txt)}</div></div>' if not self.indexable else "")
        crumbs = ""
        if pg["crumbs"]:
            lis = "".join(f'<li><a href="{self.href(path, p)}">{e(n)}</a></li>' if p != path else f'<li aria-current="page">{e(n)}</li>'
                          for p, n in pg["crumbs"])
            crumbs = f'<nav class="migas" aria-label="Ruta"><ol>{lis}</ol></nav>'
        body = (f'{aviso}<header class="top"><div class="wrap"><a class="marca" href="{self.href(path, "/")}">Ahorro <mark>Real</mark></a>'
                f'{self.nav(path)}</div></header>'
                f'<main><div class="wrap">{crumbs}{pg["body"]}</div></main>'
                f'<footer><div class="wrap"><p>{NOMBRE} reúne beneficios y precios publicados por bancos, billeteras y tiendas en Chile. '
                'No vende productos, no usa enlaces de afiliado y no recibe pago de nadie. Las condiciones pueden cambiar: '
                'manda lo que diga el emisor o la tienda.</p><p>Generado el ' + self.hoy.strftime("%d-%m-%Y") + '.</p></div></footer>')
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


# ----------------------------------------------------------------------------- piezas
def fila_beneficio(b: dict, site: Site, desde: str) -> str:
    dias = ", ".join(DIAS[d - 1].lower() for d in b["weekdays"]) if b.get("weekdays") else "días no especificados"
    partes = [dias, f'tope {clp(b["cap"])}' if b.get("cap") else "tope no informado"]
    if b.get("card_type"):
        partes.append(f'tarjeta de {"crédito" if b["card_type"] == "credito" else "débito" if b["card_type"] == "debito" else b["card_type"]}')
    if b.get("valid_to"):
        partes.append(f'hasta el {date.fromisoformat(str(b["valid_to"])).strftime("%d-%m-%Y")}')
    fuente = b.get("terms_url") or b.get("source_url")
    enlace = f' · <a href="{e(fuente)}" rel="nofollow noopener" target="_blank">condiciones</a>' if fuente else ""
    return (f'<div class="fila"><span class="pct">{b["percent"]}%</span><span class="comercio">{e(b["merchant"])}</span>'
            f'<span class="emisor">{e(b["issuer"])}</span><span class="meta">{e(" · ".join(partes))}{enlace}</span></div>')


def semana(site: Site, desde: str, conf: list[dict]) -> str:
    hoy = site.hoy.isoweekday()
    items = []
    for i, d in enumerate(DIAS_CORTOS, start=1):
        n = sum(1 for b in conf if b.get("weekdays") and i in b["weekdays"])
        cls = ' class="hoy"' if i == hoy else ""
        label = "hoy" if i == hoy else "beneficios"
        items.append(f'<li{cls}><a href="{site.href(desde, f"/beneficios/#{DIAS[i - 1].lower()}")}" '
                     f'aria-label="{DIAS[i - 1]}: {n} beneficios confirmados"><span class="d">{d}</span>'
                     f'<span class="n">{n}</span><span class="l">{label}</span></a></li>')
    return f'<ul class="semana">{"".join(items)}</ul>'


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


def build(site: Site, ofertas: dict, ben: dict | None, recon: dict) -> None:
    prod = ofertas["productos"][0]
    lista = sorted(prod["ofertas"], key=lambda o: o["precio"])
    mejor = lista[0]
    P = f'/ofertas/{prod["slug"]}/'
    bs = (ben or {}).get("benefits", [])
    conf = [b for b in bs if b["status"] == "confirmado"]
    emisores = sorted({b["issuer"] for b in bs}) if bs else []
    hoy_n = site.hoy.isoweekday()
    hoy_b = sorted([b for b in conf if b.get("weekdays") and hoy_n in b["weekdays"]], key=lambda b: -b["percent"])
    sin_dia = [b for b in conf if not b.get("weekdays")]
    ben_fecha = fecha(ben["checked_on"] + "T00:00:00") if ben else None
    site.aviso_txt = ("Prototipo con datos de muestra"
                      + (f": beneficios del {ben_fecha}" if ben else "")
                      + f" y precios del {fecha(ofertas['comprobado'])}. No son ofertas vigentes; confirma siempre con el emisor o la tienda.")

    # Hoy ---------------------------------------------------------------------------------
    if not bs:
        hoy_html = ('<p class="vacio">Todavía no hay beneficios verificados para mostrar. Estamos leyendo las páginas oficiales '
                    'de BCI, MACH y Tenpo; aquí aparecerán solo los que tengan porcentaje, comercio y días o vigencia explícitos.</p>')
    elif hoy_b:
        hoy_html = '<div class="lista">' + "".join(fila_beneficio(b, site, "/") for b in hoy_b[:8]) + "</div>"
    else:
        hoy_html = f'<p class="vacio">Ningún beneficio confirmado aplica los {DIAS_PLURAL[hoy_n - 1]}. Revisa la semana completa.</p>'
    fuente_txt = (f'{len(conf)} beneficios confirmados de {len(bs)} leídos en {", ".join(emisores)}, el {ben_fecha}.'
                  if bs else "Sin datos de beneficios todavía.")
    pasos = [("Leemos la fuente oficial", "Páginas de bancos, billeteras y tiendas, respetando sus reglas de acceso y sin forzar bloqueos."),
             ("Confirmamos o descartamos", "Un beneficio cuenta solo con porcentaje, comercio y días o vigencia explícitos. El resto queda como pista."),
             ("Calculamos lo que pagas", "Aplicamos tope y monto mínimo, y nunca sumamos promociones si no se sabe que son compatibles."),
             ("Comparamos contra la realidad", "Precio final contra el historial del producto y otras tiendas, no contra el precio tachado.")]
    site.add("/", f"{NOMBRE}: con qué tarjeta conviene pagar hoy en Chile",
             "Beneficios de bancos y billeteras en Chile verificados en la fuente oficial, ordenados por día, con tope y condiciones. "
             "Y precios comparados contra su historial real.",
             f'''<section class="stack"><p class="eyebrow">{DIAS[hoy_n - 1]} {site.hoy.strftime("%d-%m-%Y")}</p>
  <h1>¿Con qué tarjeta te <mark>conviene</mark> pagar hoy?</h1>
  <p class="lead">Beneficios de bancos y billeteras leídos en su página oficial, con tope y condiciones. Si no se puede comprobar, no lo contamos como ahorro.</p>
  {semana(site, "/", conf)}<p class="sub">{e(fuente_txt)}</p></section>
<section class="stack" aria-labelledby="hoy"><h2 id="hoy">Hoy</h2>{hoy_html}
  <p><a href="{site.href("/", "/beneficios/")}">Ver todos los beneficios de la semana</a></p></section>
<section class="duo" aria-label="Precios">
  <div class="stack-sm"><p class="eyebrow">Seguimiento de precios</p><h2>{e(prod["nombre"])}</h2>
  <p>{len(lista)} fichas reacondicionadas verificadas. {e(prod["regla_variante"])}</p></div>
  <div class="panel"><span class="eyebrow">Desde</span><span class="precio">{clp(mejor["precio"])}</span>
  <span class="sub">{e(mejor["tienda"])}, vendedor {e(mejor["vendedor"] or "no informado")}. Sin despacho ni historial todavía.</span>
  <a class="boton" href="{site.href("/", P)}">Ver el seguimiento</a></div></section>
<section class="stack" aria-labelledby="como"><h2 id="como">Cómo lo hacemos</h2><ol class="pasos">
  {"".join(f"<li><h3>{e(t)}</h3><p>{e(d)}</p></li>" for t, d in pasos)}</ol></section>''',
             jsonld=[{"@context": "https://schema.org", "@type": "WebSite", "name": NOMBRE, "url": site.base + "/", "inLanguage": "es-CL"}])

    # Beneficios por día ----------------------------------------------------------------------
    secciones = []
    for i, dia in enumerate(DIAS, start=1):
        del_dia = sorted([b for b in conf if b.get("weekdays") and i in b["weekdays"]], key=lambda b: -b["percent"])
        cuerpo = ('<div class="lista">' + "".join(fila_beneficio(b, site, "/beneficios/") for b in del_dia) + "</div>"
                  if del_dia else '<p class="vacio">Sin beneficios confirmados para este día.</p>')
        secciones.append(f'<section class="stack" id="{dia.lower()}" aria-labelledby="h-{i}"><h2 id="h-{i}">{dia}</h2>{cuerpo}</section>')
    if sin_dia:
        secciones.append('<section class="stack" id="vigencia" aria-labelledby="h-v"><h2 id="h-v">Con vigencia, sin día específico</h2>'
                         '<div class="lista">' + "".join(fila_beneficio(b, site, "/beneficios/") for b in sorted(sin_dia, key=lambda b: -b["percent"]))
                         + "</div></section>")
    resumen = ""
    if bs:
        filas = []
        for em in emisores:
            de = [b for b in bs if b["issuer"] == em]
            filas.append(f'<tr><td>{e(em)}</td><td class="num">{len(de)}</td>'
                         f'<td class="num">{sum(b["status"] == "confirmado" for b in de)}</td>'
                         f'<td class="num">{sum(b["status"] == "sin_confirmar" for b in de)}</td>'
                         f'<td class="num">{sum(b["status"] == "vencido" for b in de)}</td></tr>')
        resumen = ('<div class="tabla"><table><thead><tr><th scope="col">Emisor</th><th scope="col">Leídos</th><th scope="col">Confirmados</th>'
                   '<th scope="col">Sin confirmar</th><th scope="col">Vencidos</th></tr></thead><tbody>' + "".join(filas) + "</tbody></table></div>")
    site.add("/beneficios/", f"Beneficios bancarios por día en Chile · {NOMBRE}",
             "Descuentos de bancos y billeteras en Chile ordenados de lunes a domingo, solo los confirmados en la fuente oficial, "
             "con tope, tipo de tarjeta y enlace a las condiciones.",
             f'''<section class="stack"><p class="eyebrow">Semana completa</p><h1>Beneficios por día</h1>
  <p class="lead">Solo beneficios confirmados en la página oficial del emisor. Los que no traen porcentaje, comercio o días quedan fuera de esta lista.</p>
  {semana(site, "/beneficios/", conf)}{resumen}</section>{"".join(secciones)}''',
             crumbs=[("/", "Hoy"), ("/beneficios/", "Beneficios")])

    # Seguimiento del producto ----------------------------------------------------------------
    v, motivos = veredicto(mejor, dias_historial=0)
    filas_o = "".join(f'<tr><td class="num">{clp(o["precio"])}</td><td>{e(o["titulo"])}<div class="sub">{e(o["tienda"])} · '
                      f'vendedor {e(o["vendedor"] or "no informado")}</div></td>'
                      f'<td><a href="{e(o["url"])}" rel="nofollow noopener" target="_blank">Ver ficha</a></td></tr>' for o in lista)
    estado_cls = {"legible": "ok", "bloqueada": "bad", "pendiente": "warn"}
    tiendas = "".join(f'<tr><td>{e(t["tienda"])}</td><td><span class="pill {estado_cls[t["estado"]]}">{e(t["estado"])}</span></td><td>{e(t["detalle"])}</td></tr>'
                      for t in prod["estado_tiendas"])
    desc = "".join(f'<li>{e(d["motivo"])}{f" ({d['cantidad']})" if d["cantidad"] else ""} · {e(d["tienda"])}</li>' for d in prod["descartadas"])
    site.add(P, f'{prod["nombre"]}: precios verificados en Chile · {NOMBRE}',
             f'Seguimiento del {prod["nombre"]} en tiendas chilenas: precio de ficha verificado por condición, vendedor, '
             'ofertas descartadas y por qué.',
             f'''<section class="duo"><div class="stack"><p class="eyebrow">{e(prod["categoria"])} · {e(prod["marca"])}</p>
  <h1>{e(prod["nombre"])}</h1><p class="lead">{e(prod["regla_variante"])} Nuevo, reacondicionado y seminuevo se comparan por separado.</p>
  <div class="veredicto" role="status"><strong>{v}</strong><ul class="motivos">{"".join(f"<li>{e(m)}</li>" for m in motivos)}</ul></div></div>
  <div class="panel"><span class="eyebrow">Mejor precio reacondicionado</span><span class="precio">{clp(mejor["precio"])}</span><dl class="kv">
  <dt>Tienda</dt><dd>{e(mejor["tienda"])}</dd><dt>Vendedor</dt><dd>{e(mejor["vendedor"] or "no informado")}</dd>
  <dt>Despacho</dt><dd>sin verificar</dd><dt>Referencia real</dt><dd>sin historial</dd><dt>Ahorro real</dt><dd>no calculable</dd></dl>
  <p class="sub">Comprobado el {fecha(ofertas["comprobado"])}.</p></div></section>
<section class="stack" aria-labelledby="reac"><h2 id="reac">Reacondicionado</h2>
  <div class="tabla"><table><thead><tr><th scope="col">Precio</th><th scope="col">Producto en la ficha</th><th scope="col">Enlace</th></tr></thead><tbody>{filas_o}</tbody></table></div></section>
<section class="stack" aria-labelledby="nuevo"><h2 id="nuevo">Nuevo y seminuevo</h2>
  <p>Sin ofertas verificadas. Apple dejó de vender este modelo nuevo en 2024, y las fichas que se marcaban como nuevas no lo decían en el título, así que se descartaron.</p></section>
<section class="stack" aria-labelledby="desc"><h2 id="desc">Descartadas y por qué</h2><ul class="motivos">{desc}</ul></section>
<section class="stack" aria-labelledby="tiendas"><h2 id="tiendas">Tiendas revisadas</h2>
  <div class="tabla"><table><thead><tr><th scope="col">Tienda</th><th scope="col">Estado</th><th scope="col">Detalle</th></tr></thead><tbody>{tiendas}</tbody></table></div></section>''',
             crumbs=[("/", "Hoy"), (P, prod["nombre"])])

    # Cómo funciona -----------------------------------------------------------------------------
    reglas = [("Beneficio confirmado", "Leído en la página oficial del emisor, con porcentaje, comercio y días o vigencia explícitos."),
              ("Sin confirmar", "Falta alguno de esos datos, o solo aparece en agregadores o comunidades. Se muestra como pista, nunca como ahorro."),
              ("Mejor camino de pago", "Para un comercio, monto y día, se compara cada tarjeta por separado aplicando tope y monto mínimo. Las promociones no se suman si su compatibilidad no está clara."),
              ("Precio final pagadero", "Precio de la ficha, menos descuentos y cupones confirmados, más despacho, comisiones y cargos obligatorios."),
              ("Referencia real", "Historial del mismo producto (mediana de 60 días) y precio en otras tiendas, nunca el precio tachado."),
              ("Variante bloqueada", "Misma capacidad y condición. Un 128 GB nunca se compara contra un 256 GB."),
              ("Cashback y puntos", "Aparte: lo que pagas hoy, lo que vuelve después y el costo neto.")]
    site.add("/como-funciona/", f"Cómo verificamos beneficios y precios · {NOMBRE}",
             "Reglas de verificación: beneficio confirmado o sin confirmar, mejor camino de pago con tope y mínimo, "
             "precio final pagadero y referencia real.",
             f'''<section class="stack"><p class="eyebrow">Método</p><h1>Cómo verificamos</h1>
  <p class="lead">No buscamos el descuento más llamativo, sino la compra más conveniente, verificable y segura.</p></section>
<div class="tabla"><table><tbody>{"".join(f'<tr><th scope="row">{e(t)}</th><td>{e(d)}</td></tr>' for t, d in reglas)}</tbody></table></div>''',
             crumbs=[("/", "Hoy"), ("/como-funciona/", "Cómo funciona")])

    # Fuentes ----------------------------------------------------------------------------------
    tipo = {"retail": "Tienda", "banco": "Banco", "billetera": "Billetera", "caja": "Caja de compensación",
            "operador": "Operador", "comparador": "Comparador"}
    leg = {"ok": ("legible", "ok"), "partial": ("parcial", "warn"), "blocked": ("no legible", "bad"), "unknown": ("sin probar", "warn")}
    filas_f = "".join(f'<tr><td>{e(s["name"])}</td><td>{e(tipo.get(s["kind"], s["kind"]))}</td>'
                      f'<td><span class="pill {leg[s["readable"]][1]}">{leg[s["readable"]][0]}</span></td></tr>' for s in recon["sources"])
    n = len(recon["sources"])
    nok = sum(s["readable"] == "ok" for s in recon["sources"])
    site.add("/fuentes/", f"Fuentes revisadas en Chile · {NOMBRE}",
             f"Las {n} fuentes chilenas revisadas (bancos, billeteras, tiendas, operadores y comparadores) y cuáles se pueden leer.",
             f'''<section class="stack"><p class="eyebrow">Transparencia</p><h1>Fuentes revisadas</h1>
  <p class="lead">Revisamos {n} fuentes; {nok} se leen completas. Las que bloquean el acceso automático quedan fuera: no intentamos saltarnos esos bloqueos.</p>
  <p class="sub">Mapa del {fecha(recon["checked_at"])}.</p></section>
<div class="tabla"><table><thead><tr><th scope="col">Fuente</th><th scope="col">Tipo</th><th scope="col">Lectura</th></tr></thead><tbody>{filas_f}</tbody></table></div>''',
             crumbs=[("/", "Hoy"), ("/fuentes/", "Fuentes")])

    site.add("/404", f"Página no encontrada · {NOMBRE}", "La página que buscas no existe.",
             f'<section class="stack"><h1>Esta página no existe</h1><p><a href="{site.href("/404", "/")}">Volver a hoy</a></p></section>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["prototipo", "publico"], default="prototipo")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--hoy", help="AAAA-MM-DD (por defecto, hoy en Santiago)")
    a = ap.parse_args()
    base = os.environ.get("SITE_BASE_URL", PLACEHOLDER_URL)
    if a.modo == "publico" and base == PLACEHOLDER_URL:
        ap.error("--modo publico exige SITE_BASE_URL con el dominio definitivo")
    hoy = date.fromisoformat(a.hoy) if a.hoy else datetime.now(TZ).date()
    ofertas = json.loads((ROOT / "data" / "ofertas.json").read_text(encoding="utf8"))
    bpath = ROOT / "data" / "beneficios.json"
    ben = json.loads(bpath.read_text(encoding="utf8")) if bpath.exists() else None
    recon = json.loads(sorted((REPO / "reports").glob("recon_*.json"))[-1].read_text(encoding="utf8"))
    site = Site(a.modo, a.preview, base, hoy)
    build(site, ofertas, ben, recon)
    out = Path(a.out) if a.out else ROOT / ("preview" if a.preview else "dist")
    site.write(out)
    print(f"{len(site.pages)} páginas en {out} · modo {a.modo}{' · preview' if a.preview else ''}")


if __name__ == "__main__":
    main()
