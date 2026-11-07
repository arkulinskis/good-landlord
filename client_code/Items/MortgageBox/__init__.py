from anvil import *

from ._anvil_designer import MortgageBoxTemplate
from ... import gl, router


class MortgageBox(MortgageBoxTemplate):
    """Property page: one loan (lender, rate, payment, owed today, interest this year, renewal, paid off).
    item = gl.vm("mortgagesVM") row + property_id. Edit raises x-edit-mortgage (mortgage_id=...)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m = self.item
        d = self.dom_nodes
        d["lender"].textContent = m.get("lender") or "·"
        d["rate"].textContent = "%s%%" % m["rate"]
        d["payment"].textContent = gl.money(m["payment"], cents=True)
        d["freq"].textContent = m.get("freq") or ""
        d["balance"].textContent = gl.money(m["balance"])
        d["interest"].textContent = gl.money(m["interestYear"])
        d["renews"].textContent = gl.fmt_date(m["renews"])
        d["payoff"].textContent = gl.fmt_date(m["payoff"], "mys")
        d["calc"].setAttribute("href", router.href("deal", m["property_id"], "mortgage"))

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-edit-mortgage", mortgage_id=self.item["id"])
