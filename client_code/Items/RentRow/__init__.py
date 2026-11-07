from anvil import *

from ._anvil_designer import RentRowTemplate
from ... import gl, state


class RentRow(RentRowTemplate):
    """Money -> Rent roll: one tenancy this month: paid (the amount opens the entry), late, due today, due in N days.
    item = {t: tenancy, paid: entry or None, days: days since the due date}. Raises x-paid / x-entry."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t, paid, days = self.item["t"], self.item["paid"], self.item["days"]
        d = self.dom_nodes
        d["name"].textContent = t["tenant_name"]
        d["where"].textContent = t["property_name"] + (" · " + t["unit"] if t.get("unit") else "") + " · day %d" % t["due_day"]
        if paid:
            d["badge"].className, d["badge"].textContent = "ui-badge good", "Paid " + gl.fmt_date(paid["date"], "dm")
        elif days > 0:
            d["badge"].className, d["badge"].textContent = "ui-badge " + ("bad" if days > 5 else "warn"), "Late " + state.plural(days, "day")
        elif days == 0:
            d["badge"].className, d["badge"].textContent = "ui-badge warn", "Due today"
        else:
            d["badge"].className, d["badge"].textContent = "ui-badge", "Due in " + state.plural(-days, "day")
        self.paid_button.visible = not paid
        self.entry_button.visible = bool(paid)
        self.paid_button.text = "Paid " + gl.money(t["rent"])
        self.entry_button.text = gl.money(paid["amount"]) if paid else ""

    @handle("paid_button", "click")
    def paid_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-paid", tenancy=self.item["t"], button=self.paid_button)

    @handle("entry_button", "click")
    def entry_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-entry", entry=self.item["paid"])
