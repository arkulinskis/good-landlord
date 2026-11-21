from anvil import *

from ._anvil_designer import RoomRowTemplate
from ... import state

CONDITIONS = ["Good", "Worn", "Damaged", "Missing"]


class RoomRow(RoomRowTemplate):
    """Condition report dialog: one room to fill in (name, Good / Worn / Damaged / Missing, note). Edits go straight
    into self.item (the dialog reads its list back). Remove raises x-remove (key=item['key']) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.name_box.text = r.get("name") or ""
        self.cond_box.items = CONDITIONS
        self.cond_box.selected_value = r.get("condition") if r.get("condition") in CONDITIONS else "Good"
        self.note_box.text = r.get("note") or ""
        state.set_control_attr(self.name_box, "maxlength", 40)
        state.set_control_attr(self.note_box, "maxlength", 300)
        state.set_control_attr(self.cond_box, "aria-label", "Condition of " + (r.get("name") or "this room"))
        state.set_control_attr(self.remove_button, "aria-label", "Remove " + (r.get("name") or "this room"))

    @handle("name_box", "change")
    def name_box_change(self, **event_args):
        self.item["name"] = self.name_box.text

    @handle("cond_box", "change")
    def cond_box_change(self, **event_args):
        self.item["condition"] = self.cond_box.selected_value

    @handle("note_box", "change")
    def note_box_change(self, **event_args):
        self.item["note"] = self.note_box.text

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        if self.parent:
            self.parent.raise_event("x-remove", key=self.item.get("key"))
