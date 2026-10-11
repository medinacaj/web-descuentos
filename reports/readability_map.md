# Mapa de legibilidad — fase 0
Comprobado: 2026-10-10T22:12:31-03:00 (America/Santiago) · runner: GitHub Actions 1000000009
Fuentes revisadas: **21** · 🟢 ok: 5 · 🟡 parcial: 9 · 🔴 bloqueado: 6 · ⚪ desconocido: 1

| Fuente | Tipo | Legible | Producto | Promos | API | Evidencia |
|---|---|---|---|---|---|---|
| Falabella | retail | 🟢 ok | ok | ok_js | — | IPhone 15 Pro 256GB - Azul - Reacondicionado Por M → 799990 |
| Paris | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Ripley | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Lider | retail | 🟡 parcial | ok | url_invalida | — | iphone 15 pro 256gb (1000+) iPhone 15 Pro Max 256G → 979990 |
| Hites | retail | 🟢 ok | ok | ok | — | Iphone 15 Pro 256gb Black Titanium Reacondicionado → 849990 |
| PC Factory | retail | 🟡 parcial | precios_sin_muestra | ok_js | — | 32 menciones de % / 2 de dcto/beneficio |
| SP Digital | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Mercado Libre | retail | 🔴 bloqueado | login | login | robots |  |
| Apple Store Chile | retail | 🟡 parcial | precios_sin_muestra | url_invalida | — |  |
| MacOnline (distribuidor Apple) | retail | 🟡 parcial | url_invalida | sin_datos | — |  |
| BCI | banco | 🟢 ok | — | ok_js | — | 10 menciones de % / 18 de dcto/beneficio |
| Banco de Chile | banco | 🟡 parcial | — | sin_datos | — |  |
| Santander Chile | banco | 🔴 bloqueado | — | bloqueado | — |  |
| MACH | billetera | 🟢 ok | — | ok | — | 7 menciones de % / 11 de dcto/beneficio |
| Tenpo | billetera | 🟢 ok | — | ok | — | 7 menciones de % / 10 de dcto/beneficio |
| Caja Los Andes | caja | ⚪ desconocido | — | url_invalida | — |  |
| Entel | operador | 🟡 parcial | precios_sin_muestra | ok | — | 6 menciones de % / 16 de dcto/beneficio |
| Movistar | operador | 🟡 parcial | url_invalida | sin_datos | — |  |
| WOM | operador | 🟡 parcial | precios_sin_muestra | ok | — | 14 menciones de % / 38 de dcto/beneficio |
| SoloTodo | comparador | 🟡 parcial | robots | — | precios_sin_muestra | Apple EarPods w/ Lightning Connector (MWTY3AM/A) →  |
| Knasta | comparador | 🔴 bloqueado | bloqueado | — | — |  |

## Causas por fuente

- **Falabella**: product: HTML estático; promos: requiere navegador (JS dinámico)
  - promos: URL descubierta https://www.falabella.com/falabella-cl/page/ultimas-oportunidades?sid=HO_ABV_OFE_22 (la configurada dio url_invalida)
- **Paris**: product: bloqueo/WAF (http_403, HTTP 403); promos: bloqueo/WAF (http_403, HTTP 403)
- **Ripley**: product: bloqueo/WAF (cloudflare, HTTP 403); promos: bloqueo/WAF (cloudflare, HTTP 403)
- **Lider**: product: HTML estático; promos: 404/not-found: la ruta de prueba no existe
- **Hites**: product: HTML estático; promos: HTML estático
- **PC Factory**: product: lee precios (con navegador) pero no apareció el producto de ejemplo; promos: requiere navegador (JS dinámico)
  - promos: URL descubierta https://www.pcfactory.cl/cyber (la configurada dio sin_datos)
- **SP Digital**: product: bloqueo/WAF (cloudflare, HTTP 403); promos: bloqueo/WAF (cloudflare, HTTP 403)
- **Mercado Libre**: api: robots.txt prohíbe la ruta; no se pidió; product: exige login/verificación de cuenta o token; promos: exige login/verificación de cuenta o token
- **Apple Store Chile**: product: lee precios (con navegador) pero no apareció el producto de ejemplo; promos: 404/not-found: la ruta de prueba no existe
- **MacOnline (distribuidor Apple)**: product: 404/not-found: la ruta de prueba no existe; promos: la página carga pero no se detectan precios/beneficios
  - promos: URL descubierta https://www.maconline.com/t/accesorios?search%5Btaxon_ids%5D=836 (la configurada dio url_invalida)
- **BCI**: promos: requiere navegador (JS dinámico)
- **Banco de Chile**: promos: la página carga pero no se detectan precios/beneficios
- **Santander Chile**: promos: bloqueo/WAF (http_403, HTTP 403)
- **MACH**: promos: HTML estático
- **Tenpo**: promos: HTML estático
- **Caja Los Andes**: promos: 404/not-found: la ruta de prueba no existe
- **Entel**: product: lee precios (con navegador) pero no apareció el producto de ejemplo; promos: HTML estático
  - promos: URL descubierta https://www.entel.cl/planes/oferta-portabilidad (la configurada dio sin_datos)
- **Movistar**: product: 404/not-found: la ruta de prueba no existe; promos: la página carga pero no se detectan precios/beneficios
  - promos: URL descubierta https://ww2.movistar.cl/ofertas/convenios-corporativos/ (la configurada dio url_invalida)
- **WOM**: product: lee precios (con navegador) pero no apareció el producto de ejemplo; promos: HTML estático
- **SoloTodo**: api: lee precios (HTML estático) pero no apareció el producto de ejemplo; product: robots.txt prohíbe la ruta; no se pidió
- **Knasta**: product: bloqueo/WAF (http_403, HTTP 403)

_Las muestras de precio son evidencia de legibilidad, no precios validados para alertas._
