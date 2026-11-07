from anvil import *

from ._anvil_designer import BadgeRowTemplate


class BadgeRow(BadgeRowTemplate):
    """A landlord response badge ("Usually replies in 3 hours"). item = {icon, text}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["icon"].className = "ic ic-" + self.item["icon"]
        self.dom_nodes["text"].textContent = self.item["text"]
