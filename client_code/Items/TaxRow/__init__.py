from anvil import *

from ._anvil_designer import TaxRowTemplate
from ... import gl


class TaxRow(TaxRowTemplate):
    """Money -> Tax summary: one line. item = {label, amount, note?, auto?, total?}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        d["row"].classList.toggle("tot", bool(r.get("total")))
        d["label"].textContent = r["label"]
        d["note"].textContent = r.get("note") or ""
        d["auto"].hidden = not r.get("auto")
        d["amount"].textContent = gl.money(r["amount"], cents=True)
