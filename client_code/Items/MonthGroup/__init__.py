from anvil import *

from ._anvil_designer import MonthGroupTemplate
from ... import gl


class MonthGroup(MonthGroupTemplate):
    """Money -> Ledger: one month of entries with its total. item = {ym, entries}. Passes x-entry up."""

    def __init__(self, **properties):
        super().__init__(**properties)
        es = self.item["entries"]
        total = sum(e["amount"] if e["kind"] == "income" else -e["amount"] for e in es)
        self.dom_nodes["title"].textContent = gl.month_name(self.item["ym"])
        self.dom_nodes["sum"].textContent = gl.signed(total)
        self.dom_nodes["sum"].className = "num gl-" + gl.tone(total)
        self.rows_panel.items = es
        self.rows_panel.add_event_handler("x-entry", self._entry)

    def _entry(self, entry, **event_args):
        if self.parent:
            self.parent.raise_event("x-entry", entry=entry)
