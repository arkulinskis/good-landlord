from anvil import *

from ._anvil_designer import TenantGroupTemplate


class TenantGroup(TenantGroupTemplate):
    """Tenants: the tenancies of one property. item = {p: property, tenancies: [...]}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item["p"]
        self.dom_nodes["name"].textContent = p["name"]
        self.house.show(door=p["door"], kind=p["kind"], size=30)
        self.cards_panel.items = self.item["tenancies"]
