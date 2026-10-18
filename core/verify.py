"""Verificación conservadora de ofertas: ninguna muestra de búsqueda es precio final."""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import re

ALLOWED_STORES = {
    "falabella": {"falabella.com"},
    "hites": {"hites.com"},
    "lider": {"lider.cl"},
}
CONDITIONS = {"nuevo","reacondicionado","seminuevo"}

def _model_ok(title):
    t = re.sub(r"\s+"," ",title.casefold().strip())
    return bool(re.search(r"\biphone\s*15\s*pro\b",t)) and not re.search(r"\bpro\s*max\b",t) \
        and bool(re.search(r"\b256\s*(?:gb|gigas?)\b",t)) and not re.search(r"\b128\s*gb\b",t)

def verify_offer(item, now=None):
    """(bool, reason); solo productos con URL directa, condición y stock acreditados."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(item,dict): return False, "estructura"
    store=item.get("source_id")
    if store not in ALLOWED_STORES: return False,"fuente no seleccionada"
    try:
        u=urlparse(item.get("url",""))
        if u.scheme != "https" or not any(u.hostname == d or u.hostname.endswith("."+d) for d in ALLOWED_STORES[store]): return False,"URL de tienda"
        if not u.path or re.search(r"/(search|buscar|ofertas|category|categorias?)\b",u.path,re.I): return False,"no es ficha de producto"
    except (ValueError,AttributeError,TypeError): return False,"URL inválida"
    if not _model_ok(str(item.get("title",""))): return False,"variante/modelo no demostrados"
    if item.get("condition") not in CONDITIONS: return False,"condición no confirmada"
    if item.get("currency") != "CLP": return False,"moneda"
    p=item.get("price_clp")
    if not isinstance(p,int) or isinstance(p,bool) or p <= 0: return False,"precio final no comprobado"
    if item.get("in_stock") is not True: return False,"stock no comprobado"
    if not item.get("price_evidence") or len(str(item["price_evidence"]).strip()) < 15: return False,"falta evidencia"
    try:
        t=datetime.fromisoformat(item["captured_at"].replace("Z","+00:00"))
        if t.tzinfo is None or t > now+timedelta(minutes=5) or now-t > timedelta(hours=48):
            return False,"muestra desactualizada"
    except (ValueError,KeyError,TypeError): return False,"fecha de captura"
    return True,"verificado en la muestra"
