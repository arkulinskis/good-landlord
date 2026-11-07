from anvil import *

from ._anvil_designer import StreetHouseTemplate
from ... import router


class StreetHouse(StreetHouseTemplate):
    """Home: one house on the street (windows glow with its cash flow, smoke when it makes money). Links to the property.
    item = {id, name, door, kind, glow, smoke}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        d = self.dom_nodes
        d["link"].setAttribute("href", router.href("property", p["id"]))
        d["link"].setAttribute("title", p["name"])
        d["lbl"].textContent = p["name"]
        self.house.show(door=p["door"], kind=p["kind"], glow=p["glow"], smoke=p["smoke"], size=104)
