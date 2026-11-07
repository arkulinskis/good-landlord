import anvil.js
from anvil import *

from ._anvil_designer import SliderTemplate

_n = [0]


class Slider(SliderTemplate):
    """A range input with a label, the shown value and optional end labels. Raises "change" while it moves."""

    def __init__(self, **properties):
        self._label = ""
        self._value = 0.0
        self._ready = False
        super().__init__(**properties)
        _n[0] += 1
        d = self.dom_nodes
        rid = "gl-slider-%d" % _n[0]
        d["range"].id = rid
        d["lbl"].setAttribute("for", rid)
        d["lbl"].textContent = self._label
        d["range"].addEventListener("input", anvil.js.report_exceptions(self._moved))
        self._ready = True

    def _moved(self, event):
        try:
            self._value = float(self.dom_nodes["range"].value)
        except ValueError:
            return
        self.raise_event("change")

    def setup(self, minimum, maximum, step, value, low_end="", high_end=""):
        d = self.dom_nodes
        r = d["range"]
        r.min, r.max, r.step = str(minimum), str(maximum), str(step)
        self.value = value
        d["lo"].textContent = low_end
        d["hi"].textContent = high_end
        d["ends"].hidden = not (low_end or high_end)

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, v):
        self._label = v or ""
        if self._ready:
            self.dom_nodes["lbl"].textContent = self._label

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = float(v or 0)
        self.dom_nodes["range"].value = str(self._value)

    @property
    def shown(self):
        return str(self.dom_nodes["out"].textContent)

    @shown.setter
    def shown(self, v):
        self.dom_nodes["out"].textContent = v or ""
