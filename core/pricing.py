"""Comparación por condición sin mezclar nuevo/reacondicionado/seminuevo."""
from .verify import verify_offer

def grouped_offers(items, now=None):
    result={"nuevo":[],"reacondicionado":[],"seminuevo":[]}
    rejected=[]
    for it in items:
        ok,reason=verify_offer(it,now)
        if not ok:
            rejected.append({"source_id": it.get("source_id") if isinstance(it,dict) else None,"reason":reason})
            continue
        result[it["condition"]].append(it)
    for condition in result:
        result[condition].sort(key=lambda x:x["price_clp"])
    return {"verified_by_condition":result,"rejected":rejected,"alerts_ready":False,
            "note":"Análisis preliminar: validar términos finales y elegibilidad antes de avisar."}
