import unittest
from datetime import datetime,timezone
from core.pricing import grouped_offers
from core.verify import verify_offer

NOW=datetime(2026,10,18,15,0,tzinfo=timezone.utc)
GOOD={"source_id":"hites","url":"https://www.hites.com/producto-12345","title":"iPhone 15 Pro 256 GB",
      "condition":"reacondicionado","currency":"CLP","price_clp":849990,"in_stock":True,
      "price_evidence":"Precio final mostrado junto al producto, sujeto a verificación comercial",
      "captured_at":"2026-10-18T14:00:00Z"}

class Phase1Tests(unittest.TestCase):
    def test_accepts_valid_sample_not_live_price(self):
        self.assertEqual(verify_offer(GOOD,NOW)[0],True)
    def test_rejects_max_search_stale_and_unknown_stock(self):
        for edits in [
          {"title":"iPhone 15 Pro Max 256GB"},{"title":"iPhone 15 Pro 128GB"},
          {"url":"https://www.hites.com/search?q=iphone"},
          {"captured_at":"2026-10-10T00:00:00Z"},
          {"in_stock":False},{"condition":"desconocido"}
        ]:
            bad={**GOOD,**edits}
            self.assertFalse(verify_offer(bad,NOW)[0])
    def test_group_does_not_mix_conditions_or_enable_alerts(self):
        b={**GOOD,"source_id":"falabella","url":"https://www.falabella.com/falabella-cl/producto-456",
           "condition":"nuevo","price_clp":990000}
        r=grouped_offers([GOOD,b],NOW)
        self.assertEqual(len(r["verified_by_condition"]["nuevo"]),1)
        self.assertEqual(len(r["verified_by_condition"]["reacondicionado"]),1)
        self.assertFalse(r["alerts_ready"])

if __name__=="__main__": unittest.main()
