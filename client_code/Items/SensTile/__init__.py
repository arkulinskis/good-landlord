from anvil import *

from ._anvil_designer import SensTileTemplate
from ... import gl


class SensTile(SensTileTemplate):
    """Deal check: profit after N years if prices grew by a% a year; tap to try it. item = {a, profit, t, on}.
    Raises x-appr (value=a)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        d = self.dom_nodes
        col = "var(--gl-s1)" if s["profit"] >= 0 else "var(--gl-s2)"
        d["btn"].style.background = "color-mix(in srgb, %s %d%%, var(--c-surface))" % (col, round(8 + s["t"] * 30))
        d["btn"].classList.toggle("on", bool(s.get("on")))
        d["btn"].setAttribute("aria-pressed", "true" if s.get("on") else "false")
        d["btn"].setAttribute("title", gl.money(s["profit"]))
        d["btn"].setAttribute("data-key", str(s["a"]))
        d["a"].textContent = ("+" if s["a"] > 0 else "") + ("%g" % s["a"]) + "%"
        d["p"].textContent = gl.money(s["profit"], short=True, sign=True)

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-appr", value=self.item["a"])
