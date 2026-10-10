# Mapa de legibilidad — fase 0
Comprobado: 2026-10-10T16:12:14-03:00 (America/Santiago) · runner: GitHub Actions 1000000006
Fuentes revisadas: **21** · 🟢 ok: 6 · 🟡 parcial: 7 · 🔴 bloqueado: 6 · ⚪ desconocido: 2

| Fuente | Tipo | Legible | Producto | Promos | API | Evidencia |
|---|---|---|---|---|---|---|
| Falabella | retail | 🟡 parcial | ok | sin_datos | — | IPhone 15 Pro 256GB - Azul - Reacondicionado Por M → 799990 |
| Paris | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Ripley | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Lider | retail | 🟡 parcial | ok | bloqueado | — | iphone 15 pro 256gb (1000+) iPhone 15 Pro Max 256G → 979990 |
| Hites | retail | 🟢 ok | ok | ok | — | Iphone 15 Pro 256gb Black Titanium Reacondicionado → 849990 |
| PC Factory | retail | 🟡 parcial | ok_js | sin_datos | — |  |
| SP Digital | retail | 🔴 bloqueado | bloqueado | bloqueado | — |  |
| Mercado Libre | retail | 🟡 parcial | sin_datos | sin_datos | robots |  |
| Apple Store Chile | retail | 🟡 parcial | ok_js | url_invalida | — |  |
| MacOnline (distribuidor Apple) | retail | ⚪ desconocido | url_invalida | url_invalida | — |  |
| BCI | banco | 🔴 bloqueado | — | bloqueado | — |  |
| Banco de Chile | banco | 🟡 parcial | — | sin_datos | — |  |
| Santander Chile | banco | 🔴 bloqueado | — | bloqueado | — |  |
| MACH | billetera | 🟢 ok | — | ok | — | 7 menciones de % / 11 de dcto/beneficio |
| Tenpo | billetera | 🟢 ok | — | ok | — | 7 menciones de % / 10 de dcto/beneficio |
| Caja Los Andes | caja | ⚪ desconocido | — | url_invalida | — |  |
| Entel | operador | 🟡 parcial | ok_js | sin_datos | — |  |
| Movistar | operador | 🟢 ok | ok | ok | — | 3 menciones de % / 3 de dcto/beneficio |
| WOM | operador | 🟢 ok | ok_js | ok | — | 14 menciones de % / 38 de dcto/beneficio |
| SoloTodo | comparador | 🟢 ok | robots | — | ok | Apple EarPods w/ Lightning Connector (MWTY3AM/A) →  |
| Knasta | comparador | 🔴 bloqueado | bloqueado | — | — |  |

## Causas por fuente

- **Falabella**: product: HTML estático; promos: la página carga pero no se detectan precios/beneficios
- **Paris**: product: bloqueo/WAF (http_403); promos: bloqueo/WAF (http_403)
- **Ripley**: product: bloqueo/WAF (cloudflare); promos: bloqueo/WAF (cloudflare)
- **Lider**: product: HTML estático; promos: bloqueo/WAF (perimeterx)
- **Hites**: product: HTML estático; promos: HTML estático
- **PC Factory**: product: requiere navegador (JS dinámico); promos: la página carga pero no se detectan precios/beneficios
- **SP Digital**: product: bloqueo/WAF (cloudflare); promos: bloqueo/WAF (cloudflare)
- **Mercado Libre**: api: robots.txt prohíbe la ruta; no se pidió; product: la página carga pero no se detectan precios/beneficios; promos: la página carga pero no se detectan precios/beneficios
- **Apple Store Chile**: product: requiere navegador (JS dinámico); promos: 404: la ruta de prueba no existe; corregir URL
- **MacOnline (distribuidor Apple)**: product: 404: la ruta de prueba no existe; corregir URL; promos: 404: la ruta de prueba no existe; corregir URL
- **BCI**: promos: bloqueo/WAF (cloudflare)
- **Banco de Chile**: promos: la página carga pero no se detectan precios/beneficios
- **Santander Chile**: promos: bloqueo/WAF (http_403)
- **MACH**: promos: HTML estático
- **Tenpo**: promos: HTML estático
- **Caja Los Andes**: promos: 404: la ruta de prueba no existe; corregir URL
- **Entel**: product: requiere navegador (JS dinámico); promos: la página carga pero no se detectan precios/beneficios
- **Movistar**: product: HTML estático; promos: HTML estático
- **WOM**: product: requiere navegador (JS dinámico); promos: HTML estático
- **SoloTodo**: api: API pública; product: robots.txt prohíbe la ruta; no se pidió
- **Knasta**: product: bloqueo/WAF (http_403)

_Las muestras de precio son evidencia de legibilidad, no precios validados para alertas._
