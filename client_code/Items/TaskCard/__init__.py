from anvil import *

from ._anvil_designer import TaskCardTemplate
from ... import gl


class TaskCard(TaskCardTemplate):
    """A repair request or task: status, urgent, number, title, when (and where, on the board).
    item = a task dict (+ "show_where"). A click raises x-task (task=...) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        k = self.item
        d = self.dom_nodes
        d["chip"].className = "gl-status gl-st-" + k["status"]
        d["chip"].textContent = gl.STATUS_LABEL.get(k["status"], k["status"])
        d["urgent"].hidden = k.get("priority") != "urgent"
        d["num"].textContent = "#%d" % (k.get("number") or 0)
        d["title"].textContent = k["title"]
        d["sub"].textContent = ((k.get("where") or "") + " · " if k.get("show_where") else "") + gl.task_when(k)
        d["btn"].setAttribute("data-key", k["id"])

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-task", task=self.item)
