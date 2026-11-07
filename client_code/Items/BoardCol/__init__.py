from anvil import *

from ._anvil_designer import BoardColTemplate


class BoardCol(BoardColTemplate):
    """Tenants -> Requests: one status column of the board. item = {title, tasks}. Passes x-task up."""

    def __init__(self, **properties):
        super().__init__(**properties)
        ks = self.item["tasks"]
        self.dom_nodes["title"].textContent = self.item["title"]
        self.dom_nodes["count"].textContent = str(len(ks))
        self.tasks_panel.items = ks
        self.empty.visible = not ks
        self.tasks_panel.add_event_handler("x-task", self._task)

    def _task(self, task, **event_args):
        if self.parent:
            self.parent.raise_event("x-task", task=task)
