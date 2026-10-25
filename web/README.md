# Ahorro Real — sitio público (prototipo, nombre provisional)

Sitio estático generado por `web/build.py` desde datos del sistema: `web/data/ofertas.json` (salida del recolector, PR #7) y el último `reports/recon_*.json`. Ningún precio se escribe a mano; `tests/test_web.py` falla si aparece un precio que no está en los datos.

```
python web/build.py                                    # prototipo → web/dist (noindex, robots bloqueado)
python web/build.py --preview                          # enlaces relativos para la vista previa
SITE_BASE_URL=https://dominio.cl python web/build.py --modo publico   # producción
```

Páginas: inicio, seguimiento por producto (`/ofertas/<slug>/`), método (`/como-funciona/`), fuentes (`/fuentes/`), 404.

## SEO técnico
| Elemento | Prototipo | Público |
|---|---|---|
| `meta robots` | `noindex, nofollow` (a propósito: precios de muestra) | `index, follow` |
| `robots.txt` | `Disallow: /` | `Allow: /` + `Sitemap:` |
| `sitemap.xml` | no se genera | URLs absolutas canónicas, sin 404 |
| canonical, title y description únicos, OG, `lang="es-CL"` | sí | sí |
| Datos estructurados | `WebSite`, `BreadcrumbList` | ídem. No se marca `Product`/`Offer`: los precios son de terceros y de muestra |
| HTML estático (sin JS) | sí | sí |

## Pendiente antes de publicar (bloqueantes)
- [ ] Dominio definitivo (no se verificó disponibilidad de ningún nombre) y hosting con HTTPS y redirección www/no-www.
- [ ] Datos vigentes: recolección diaria funcionando y página regenerada en cada corrida; hoy son muestras del 24-10-2026.
- [ ] Revisar términos de uso de cada tienda sobre reutilizar precios públicos y uso nominativo de marcas (no se usan logos).
- [ ] Revisión de publicidad y exactitud de precios en Chile (Ley 19.496) por alguien habilitado; no se afirma cumplimiento.
- [ ] Contacto y página de correcciones para que una tienda o un usuario reporte un precio erróneo.
- [ ] Fuentes: hoy se cargan desde Google Fonts (envía la IP del visitante a Google); autoalojarlas antes de publicar.
- [ ] Google Search Console (requiere al propietario): verificar el dominio, enviar `sitemap.xml`, inspeccionar `/` y `/ofertas/iphone-15-pro-256gb/`, solicitar indexación, revisar cobertura y canonicalización.

## Datos personales
El sitio no tiene formularios, cookies ni analítica. Si se agregan, inventariarlos antes (ver `docs/ASESOR_LEGAL_TECNOLOGICO.md`).
