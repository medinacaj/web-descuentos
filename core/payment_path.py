"""Mejor camino de pago: qué tarjeta o billetera conviene para un comercio, monto y fecha.

Reglas (README del proyecto):
- Solo beneficios `confirmado` entran al cálculo. Los demás se listan aparte como pistas.
- Nunca se suman dos beneficios: cada opción es un solo beneficio (la compatibilidad suele estar pendiente).
- El tope y el mínimo de compra se aplican cuando el texto los informa; si no, se marca.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def merchant_matches(benefit_merchant: str | None, merchant: str) -> bool:
    a, b = _norm(benefit_merchant), _norm(merchant)
    return bool(a and b) and (a == b or re.search(rf"\b{re.escape(b)}\b", a) is not None)


def applies_to_me(benefit: dict, my_benefits: dict) -> str:
    """te_aplica: emisor y tipo de tarjeta coinciden. te_aplicaria: falta saber el tipo. no_te_aplica: otro emisor."""
    issuer = _norm(benefit["issuer"])
    mine = {_norm(x) for x in my_benefits.get("wallets", [])}
    cards: dict[str, list[dict]] = {_norm(b["issuer"]): b.get("cards") or [] for b in my_benefits.get("banks", [])}
    if issuer in mine and not cards.get(issuer):
        return "te_aplica" if benefit.get("card_type") in (None, "prepago", "debito") else "te_aplicaria"
    if issuer not in cards:
        return "no_te_aplica"
    my_types = {c.get("type") for c in cards[issuer]}
    if not my_types:
        return "te_aplicaria"
    if benefit.get("card_type") is None or benefit["card_type"] in my_types:
        return "te_aplica"
    return "no_te_aplica"


def best_paths(benefits: list[dict], merchant: str, amount: int, on: date, my_benefits: dict) -> dict:
    options, hints = [], []
    weekday = on.isoweekday()
    for b in benefits:
        if not merchant_matches(b.get("merchant"), merchant):
            continue
        if b.get("status") != "confirmado":
            hints.append({"issuer": b["issuer"], "motivo": "sin confirmar: " + ", ".join(b.get("status_reasons") or [])})
            continue
        notes = []
        if b.get("weekdays") and weekday not in b["weekdays"]:
            continue
        if not b.get("weekdays"):
            notes.append("el texto no especifica días")
        if b.get("valid_to") and b["valid_to"] < on:
            continue
        if b.get("min_purchase") and amount < b["min_purchase"]:
            continue
        saving = amount * b["percent"] // 100
        if b.get("cap") is not None:
            saving = min(saving, b["cap"])
        else:
            notes.append("tope no informado: el ahorro podría ser menor")
        if b.get("stackable") is None:
            notes.append("compatibilidad con otras promociones pendiente")
        options.append({"issuer": b["issuer"], "card_type": b.get("card_type"), "percent": b["percent"], "saving": saving,
                        "pay": amount - saving, "applies": applies_to_me(b, my_benefits), "notes": notes,
                        "source_url": b.get("source_url"), "terms_url": b.get("terms_url")})
    rank = {"te_aplica": 0, "te_aplicaria": 1, "no_te_aplica": 2}
    options.sort(key=lambda o: (-o["saving"], rank[o["applies"]]))
    return {"merchant": merchant, "amount": amount, "date": on.isoformat(), "options": options, "hints": hints}
