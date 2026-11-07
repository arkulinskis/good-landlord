from anvil import *

from ._anvil_designer import AttnRowTemplate


class AttnRow(AttnRowTemplate):
    """Home: one thing that needs the landlord (new request, unread message, late rent, renewal, visit soon).
    item = {go: '#tenancy/..', icon, cls: '' | 'warn' | 'bad', t, s}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        a = self.item
        d = self.dom_nodes
        d["link"].setAttribute("href", a["go"])
        d["dot"].className = "dot " + (a.get("cls") or "")
        d["icon"].className = "ic ic-" + a["icon"]
        d["t"].textContent = a["t"]
        d["s"].textContent = a.get("s") or ""
