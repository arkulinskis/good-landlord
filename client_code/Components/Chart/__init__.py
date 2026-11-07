import anvil.js
from anvil import *
from anvil.js import window

from ._anvil_designer import ChartTemplate


class Chart(ChartTemplate):
    """plot(fn): fn(element) draws the chart (gl.draw(...)); it is drawn again when the window is resized."""

    def __init__(self, **properties):
        self._fn = None
        self._stop = None
        super().__init__(**properties)

    def plot(self, fn):
        self._fn = fn
        self.redraw()

    def redraw(self):
        if self._fn is not None:
            self._fn(self.dom_nodes["box"])

    def _resized(self):
        self.redraw()

    @handle("", "show")
    def form_show(self, **event_args):
        if self._stop is None:
            self._stop = window.GL.onResize(anvil.js.report_exceptions(self._resized))
        self.redraw()  # the first draw can happen before the box has its width

    @handle("", "hide")
    def form_hide(self, **event_args):
        if self._stop is not None:
            self._stop()
            self._stop = None
