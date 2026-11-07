from anvil import *

from ._anvil_designer import MileRowTemplate
from ... import gl, state


class MileRow(MileRowTemplate):
    """Deal check: a milestone row (after N years: equity, cash flow a year, profit if sold). item = {y, equity, cf, profit}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        d["y"].textContent = state.plural(r["y"], "year")
        d["eq"].textContent = gl.money(r["equity"], short=True)
        d["cf"].textContent = gl.signed(r["cf"], short=True)
        d["cf"].className = "num gl-" + gl.tone(r["cf"])
        d["pr"].textContent = gl.signed(r["profit"], short=True)
        d["pr"].className = "num gl-" + gl.tone(r["profit"])
