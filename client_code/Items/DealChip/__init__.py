from anvil import *

from ._anvil_designer import DealChipTemplate
from ... import router


class DealChip(DealChipTemplate):
    """Deal check: a property chip (or the Calculator chip). item = {id, name, door, kind, on} or {calc: True, on}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        d = self.dom_nodes
        d["link"].classList.toggle("on", bool(c.get("on")))
        if c.get("on"):
            d["link"].setAttribute("aria-current", "page")
        if c.get("calc"):
            d["link"].setAttribute("href", router.href("deal", "calculator"))
            d["name"].textContent = "Calculator"
            self.house.visible = False
        else:
            d["link"].setAttribute("href", router.href("deal", c["id"]))
            d["name"].textContent = c["name"]
            d["icon"].hidden = True
            self.house.show(door=c["door"], kind=c["kind"], size=26)
