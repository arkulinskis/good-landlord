import anvil.server
from anvil import *

from ._anvil_designer import NewTaskTemplate
from ... import gl, state


class NewTask(NewTaskTemplate):
    """Ask for a repair (tenant: tenant_request) or add a task (landlord: landlord_new_task). send(title, details,
    category, priority) makes the server call. It goes into the sealed record with today's date.
    Closes with the reply or None."""

    def __init__(self, send=None, title="Ask for a repair", lead="It goes into the record with today's date.", ok="Send request", **properties):
        super().__init__(**properties)
        self._send_fn = send or _no_send
        self.title_label.text = title
        state.heading(self.title_label, 2)
        self.lead_label.text = lead
        self.save_button.text = ok
        self.cat_box.items = [(label, key) for key, label in gl.TASK_CATS]
        self.cat_box.selected_value = "other"
        self.prio_box.items = [(label, key) for key, label in gl.PRIORITIES]
        self.prio_box.selected_value = "normal"
        state.set_control_attr(self.cat_box, "aria-label", "Type")
        state.set_control_attr(self.prio_box, "aria-label", "How urgent?")
        state.set_control_attr(self.title_box, "maxlength", 120)
        state.set_control_attr(self.details_box, "maxlength", 3000)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        if not (self.title_box.text or "").strip():
            self._fail("Say what needs doing.")
            return
        self.error_label.visible = False
        self.save_button.enabled = False
        try:
            r = self._send_fn(self.title_box.text, self.details_box.text, self.cat_box.selected_value, self.prio_box.selected_value)
        finally:
            self.save_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True

    def _send(self, fn, *args):
        """Server call; an expected problem shows under the form (the dialog stays open)."""
        self.error_label.visible = False
        self.save_button.enabled = False
        try:
            r = anvil.server.call(fn, *args)
        finally:
            self.save_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return None
        return r


def _no_send(title, details, category, priority):
    return {"ok": False, "error": "Nothing to send to."}
