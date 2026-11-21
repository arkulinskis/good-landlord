from anvil import *

from ._anvil_designer import ConditionReportTemplate
from ... import state

DEFAULT_ROOMS = ["Entry", "Kitchen", "Living room", "Bedroom 1", "Bathroom", "Windows & blinds", "Appliances",
                 "Floors & walls", "Smoke & CO alarms", "Keys & meters"]


class ConditionReport(ConditionReportTemplate):
    """Write a move-in or move-out condition report (landlord: landlord_report, tenant: tenant_report).
    send(kind, rooms, note) makes the server call. kind = 'move_in' | 'move_out'. move_in_rooms = the rooms of the
    latest move-in report (a move-out report starts from them, so the two compare room by room).
    Closes with the reply or None."""

    def __init__(self, send=None, kind="move_in", move_in_rooms=None, lead="", **properties):
        super().__init__(**properties)
        self._send_fn = send
        self._move_in = [r["name"] for r in (move_in_rooms or []) if r.get("name")]
        self._n = 0
        state.heading(self.title_label, 2)
        self.lead_label.text = lead or ("Go room by room and write down anything that isn't perfect: "
                                        "it protects both of you when the deposit comes back.")
        state.set_control_attr(self.note_box, "maxlength", 600)
        state.set_control_attr(self.note_box, "aria-label", "General note")
        self.rooms_panel.add_event_handler("x-remove", self._remove)
        self.kind = kind
        self._kind(kind)

    def _rooms_for(self, kind):
        names = self._move_in if (kind == "move_out" and self._move_in) else DEFAULT_ROOMS
        out = []
        for n in names:
            self._n += 1
            out.append({"key": self._n, "name": n, "condition": "Good", "note": ""})
        return out

    def _kind(self, kind):
        rows = list(self.rooms_panel.items or [])
        untouched = all(r.get("condition") == "Good" and not r.get("note") for r in rows)
        self.kind = kind
        self.in_button.classes["on"] = kind == "move_in"
        self.out_button.classes["on"] = kind == "move_out"
        if untouched:
            self.rooms_panel.items = self._rooms_for(kind)

    def in_click(self, event):
        self._kind("move_in")

    def out_click(self, event):
        self._kind("move_out")

    def _remove(self, key, **event_args):
        self.rooms_panel.items = [r for r in self.rooms_panel.items if r["key"] != key]

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self._n += 1
        self.rooms_panel.items = list(self.rooms_panel.items or []) + [{"key": self._n, "name": "", "condition": "Good", "note": ""}]

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        rooms = [{"name": (r.get("name") or "").strip(), "condition": r.get("condition") or "Good",
                  "note": (r.get("note") or "").strip()} for r in (self.rooms_panel.items or [])]
        rooms = [r for r in rooms if r["name"]]
        if not rooms:
            self._fail("Add at least one room with a name.")
            return
        if self._send_fn is None:
            self._fail("Nothing to send to.")
            return
        self.error_label.visible = False
        self.save_button.enabled = False
        try:
            r = self._send_fn(self.kind, rooms, self.note_box.text or "")
        finally:
            self.save_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
