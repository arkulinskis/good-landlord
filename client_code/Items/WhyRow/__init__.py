from anvil import *

from ._anvil_designer import WhyRowTemplate
from ... import gl


class WhyRow(WhyRowTemplate):
    """Deal check: one part of the profit (price growth, mortgage paid down, cash flow, costs) as a bar from the middle.
    item = {label, v, w (0..50, % of the track)}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        d["label"].textContent = r["label"]
        bar = d["bar"]
        if r["v"] >= 0:
            bar.style.left, bar.style.background = "50%", "var(--gl-s1)"
        else:
            bar.style.right, bar.style.background = "50%", "var(--gl-s2)"
        bar.style.width = "%.2f%%" % r["w"]
        d["n"].textContent = gl.signed(r["v"])
        d["n"].className = "n num gl-" + gl.tone(r["v"])
