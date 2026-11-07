from anvil import *

from ._anvil_designer import PropCardTemplate
from ... import gl, router, state


class PropCard(PropCardTemplate):
    """Home: a property card (house, worth, owed, tenancies, monthly cash flow). item = {p: property, m: metrics}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p, m = self.item["p"], self.item["m"]
        d = self.dom_nodes
        d["link"].setAttribute("href", router.href("property", p["id"]))
        d["name"].textContent = p["name"]
        d["sub"].textContent = p.get("address") or gl.KIND_LABEL.get(p.get("kind"), "")
        d["worth"].textContent = gl.money(m["value"], short=True)
        d["owe"].textContent = gl.money(m["balance"], short=True)
        d["tens"].textContent = state.plural(m["tenancies"], "tenancy", "tenancies")
        d["cash"].textContent = gl.signed(m["cashMonthly"])
        d["cash"].className = "num gl-" + gl.tone(m["cashMonthly"])
        self.house.show(door=p["door"], kind=p["kind"], glow=m["glow"], size=72)
