"""Fase 2 con textos sintéticos: no se versiona HTML de los emisores."""
from datetime import date

from core.payment_path import applies_to_me, best_paths
from scrapers.banks import benefits as bn

TODAY = date(2026, 10, 25)  # domingo
MY = {"wallets": ["MACH"], "banks": [{"issuer": "BCI", "cards": []}, {"issuer": "Banco de Chile", "cards": []}]}


def page(*cards):
    return "<html><body><header><p>30% menú</p></header>" + "".join(
        f'<div class="benefit-card"><h3>{m}</h3><p>{t}</p><a href="/bases/{i}.pdf">Bases legales</a></div>'
        for i, (m, t) in enumerate(cards)) + "</body></html>"


def test_extract_and_confirm():
    html = page(("Starbucks", "40% de descuento los viernes con tarjeta de crédito. Tope $10.000 por transacción."),
                ("Cine Hoyts", "2x1 todos los días hasta el 31 de diciembre de 2026, compras online."),
                ("Sushi Go", "25% de dcto. Válido hasta el 30/09/2026."))
    bs = bn.extract(html, "https://banco.cl/beneficios", "BCI", TODAY)
    by = {b["merchant"]: b for b in bs}
    assert set(by) == {"Starbucks", "Sushi Go"}  # sin % no es bloque de beneficio; el header se ignora
    s = by["Starbucks"]
    assert (s["percent"], s["weekdays"], s["cap"], s["card_type"], s["status"]) == (40, [5], 10000, "credito", "confirmado")
    assert s["terms_url"] == "https://banco.cl/bases/0.pdf"
    assert by["Sushi Go"]["status"] == "vencido"


def test_unconfirmed_without_days_or_validity():
    b = bn.parse_benefit("20% en Restaurante X", "MACH", "https://x", None, TODAY)
    b["merchant"] = "Restaurante X"
    assert bn.status_for(b, TODAY) == ("sin_confirmar", ["sin vigencia ni días"])


def test_day_range_and_year_required():
    assert bn._days("de lunes a jueves") == [1, 2, 3, 4]
    assert bn._days("sábados y domingos") == [6, 7]
    assert bn._valid_to("válido hasta el 15 de noviembre", TODAY) is None  # sin año no se adivina
    assert bn._valid_to("vigente hasta el 15 de noviembre de 2026", TODAY) == date(2026, 11, 15)


def test_stackable_flags():
    assert bn.parse_benefit("10% los lunes, no acumulable con otras promociones", "BCI", "u", None, TODAY)["stackable"] is False
    assert bn.parse_benefit("10% los lunes", "BCI", "u", None, TODAY)["stackable"] is None


def _b(issuer, pct, days=None, cap=None, status="confirmado", card=None, min_purchase=None, merchant="Starbucks"):
    return {"issuer": issuer, "merchant": merchant, "percent": pct, "weekdays": days, "cap": cap, "status": status,
            "status_reasons": [] if status == "confirmado" else ["sin comercio identificado"], "card_type": card,
            "min_purchase": min_purchase, "valid_to": None, "stackable": None, "source_url": "u", "terms_url": None}


def test_best_path_applies_cap_day_and_never_sums():
    bs = [_b("BCI", 40, days=[7], cap=5000), _b("MACH", 20, days=[7]), _b("Tenpo", 50, days=[5]),
          _b("Santander", 60, status="sin_confirmar")]
    r = best_paths(bs, "starbucks", 30000, TODAY, MY)
    assert [(o["issuer"], o["saving"]) for o in r["options"]] == [("MACH", 6000), ("BCI", 5000)]
    assert r["options"][0]["applies"] == "te_aplica" and r["options"][1]["applies"] == "te_aplicaria"
    assert "tope no informado: el ahorro podría ser menor" in r["options"][0]["notes"]
    assert r["hints"][0]["issuer"] == "Santander"  # sin confirmar: pista, no opción


def test_min_purchase_and_other_issuer():
    assert best_paths([_b("BCI", 30, days=[7], min_purchase=50000)], "Starbucks", 30000, TODAY, MY)["options"] == []
    assert applies_to_me(_b("Santander", 10), MY) == "no_te_aplica"
