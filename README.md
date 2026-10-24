# Analista de Descuentos Chile

Sistema automatizado que detecta compras realmente convenientes en Chile (precio final verificable, no el descuento más llamativo).
Recolección en Python (httpx + Playwright), datos en Supabase, ejecución diaria en GitHub Actions, criterio y redacción con la API de Claude solo para candidatos filtrados, alertas por Gmail.

## Estado: fase 0 (reconocimiento)

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Mapa de legibilidad de fuentes | en curso |
| 1 | Esquema, 3 tiendas, 10 productos, correo diario | pendiente de aprobación |
| 2 | Cupones y beneficios bancarios, mejor camino de pago | — |
| 3 | Radar por categorías, registro de fuentes que crece solo | — |
| 4 | Panel web (opcional) | — |

## Fase 0
- `config/sources.yaml`: registro de fuentes con URLs de prueba (producto de ejemplo y promociones).
- `tools/recon.py`: prueba cada fuente respetando robots.txt, ≥4 s entre peticiones al mismo host, primero HTML estático y luego navegador solo si hace falta. No es un scraper definitivo.
- Se ejecuta en GitHub Actions (`.github/workflows/recon.yml`, manual o al cambiar las fuentes) porque es el mismo entorno donde correrá el sistema diario. El mapa queda en `reports/readability_map.md` y el detalle en `reports/recon_<fecha>.json`.

Local: `pip install -r requirements.txt && python -m playwright install chromium && python -m tools.recon --only falabella`

## Credenciales (solo variables de entorno / GitHub Secrets)
Ver `.env.example`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ALERT_TO`. Nunca se guardan en el código. Se necesitan a partir de la fase 1.

## Base de datos
`db/schema.sql` se ejecuta tal cual en el editor SQL de Supabase (idempotente, RLS activado; el sistema usa la service key).

## Fase 1 · Controles de datos (P1, 18-10-2026)

Fuentes iniciales seleccionadas: Falabella y Hites (legibilidad técnica satisfactoria en fase 0), Líder (parcial, solo búsqueda de producto). Registro: `config/phase1_sources.json`. No implica disponibilidad de artículos, precios confirmados ni aceptación comercial.

`core/verify.py` exige URL directa HTTPS del dominio permitido, iPhone 15 Pro **256 GB** sin variante Max, condición explícita (nuevo/reacondicionado/seminuevo), CLP, precio positivo, stock confirmado, evidencia textual y captura reciente (48 h). `core/pricing.py` compara cada condición por separado y descarta candidatos incompletos. Ejecutar `python -m tools.phase1 archivo.json` para validar un lote. Resultados quedan en `reports/candidates_checked.json` sin activar correos ni alertas.

**Queda pendiente** un recolector real y autorizado por comercio, 10 fichas de productos con evidencias y validación final de precio/stock/condiciones. No declarar operativo el envío de alertas ni activar el cron diario sin superar esa aceptación. El mapa de fase 0 sigue siendo exploratorio.

### Recolector (Issue #4)
`python -m tools.collect` sigue búsqueda → fichas del modelo → JSON-LD de la ficha → `core/verify.py`. Workflow `collect.yml` (bajo demanda o al cambiar el recolector), sin correo ni base de datos; resultado como artefacto de 7 días.

Reglas: condición desde el título (`NewCondition` de schema.org por sí solo no confirma "nuevo"; "grado A" es ambiguo), vendedor solo si viene en la oferta (nombres del estado embebido quedan como pista), omite capacidades distintas de 256 GB antes de pedir la ficha, se detiene ante 401/403/429 sin reintentos ni evasión.

Resultado en GitHub Actions (24-10-2026):

| Fuente | Estado | Causa |
|---|---|---|
| Lider | fichas legibles | 5 reacondicionados 256 GB aceptados; vendedor no informado en la oferta |
| Falabella | fichas bloqueadas | búsqueda legible, ficha responde 403 desde GitHub Actions |
| Hites | sin enlaces a fichas | el HTML estático de la búsqueda no contiene enlaces ni JSON-LD del modelo; requiere navegador (pendiente) |
