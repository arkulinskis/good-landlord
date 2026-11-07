from anvil import *

from ._anvil_designer import HouseTemplate
from ... import gl


class House(HouseTemplate):
    """A property's house (SVG from the engine). Set door/kind/glow/smoke/size, or show(...) to set several at once."""

    def __init__(self, **properties):
        self._o = {"door": "red", "kind": "house", "glow": 0.8, "smoke": False, "size": 120}
        self._ready = False
        super().__init__(**properties)
        self._ready = True
        self._draw()

    def show(self, door=None, kind=None, glow=None, smoke=None, size=None):
        for k, v in (("door", door), ("kind", kind), ("glow", glow), ("smoke", smoke), ("size", size)):
            if v is not None:
                self._o[k] = v
        self._draw()

    def _draw(self):
        if self._ready:
            o = self._o
            self.dom_nodes["box"].innerHTML = gl.house_svg(o["door"], o["kind"], o["glow"], o["smoke"], o["size"])

    def _set(self, key, value):
        self._o[key] = value
        self._draw()

    @property
    def door(self):
        return self._o["door"]

    @door.setter
    def door(self, value):
        self._set("door", value or "red")

    @property
    def kind(self):
        return self._o["kind"]

    @kind.setter
    def kind(self, value):
        self._set("kind", value or "house")

    @property
    def glow(self):
        return self._o["glow"]

    @glow.setter
    def glow(self, value):
        self._set("glow", 0.8 if value is None else value)

    @property
    def smoke(self):
        return self._o["smoke"]

    @smoke.setter
    def smoke(self, value):
        self._set("smoke", bool(value))

    @property
    def size(self):
        return self._o["size"]

    @size.setter
    def size(self, value):
        self._set("size", value or 120)
