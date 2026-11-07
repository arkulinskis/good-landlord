from anvil import *

from ._anvil_designer import EntryRowTemplate
from ... import gl


class EntryRow(EntryRowTemplate):
    """A ledger entry (Money -> Ledger, and the property page's recent entries). A click raises x-entry (entry=...).
    item = an entry dict (+ "compact": the property page's shorter row)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        d = self.dom_nodes
        c = gl.category(e["category"])
        compact = bool(e.get("compact"))
        d["btn"].classList.toggle("compact", compact)
        d["date"].textContent = gl.fmt_date(e["date"], "dm")
        d["memo"].textContent = e.get("memo") or c["label"]
        if compact:
            d["cat"].textContent = c["label"] + " · " + gl.fmt_date(e["date"])
        else:
            p = gl.prop(e.get("property_id"))
            d["cat"].textContent = c["label"] + " · " + (p["name"] if p else "")
        claim = c.get("claim")
        d["claim"].hidden = compact or not claim
        d["claim"].textContent = {"yes": "Claimable", "capital": "Capital", "no": "Not claimable"}.get(claim, "")
        d["claim"].className = "ui-badge " + {"yes": "sage", "capital": "honey"}.get(claim, "")
        d["task"].hidden = compact or not e.get("task_id")
        income = e["kind"] == "income"
        d["amt"].textContent = ("+" if income else "−") + gl.money(e["amount"], cents=True)
        d["amt"].className = "amt num" + (" gl-pos" if income else "")

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-entry", entry=self.item)
