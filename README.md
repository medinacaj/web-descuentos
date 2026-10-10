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
