from anvil import *

from ._anvil_designer import RoomLineTemplate

COND_CLS = {"Good": "good", "Worn": "worn", "Damaged": "bad", "Missing": "bad"}


class RoomLine(RoomLineTemplate):
    """Condition report view: one room (name, condition chip, note), or one change since move-in
    (item has 'before': "Good -> Damaged"). item = {name, condition, note[, before]}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        d["name"].textContent = r["name"]
        cond = r.get("condition") or r.get("after") or ""
        d["cond"].className = "gl-cond gl-cond-" + COND_CLS.get(cond, "good")
        d["cond"].textContent = ((r["before"] + " → ") if r.get("before") else "") + cond
        d["note"].textContent = r.get("note") or ""
        d["note"].hidden = not r.get("note")
