import anvil.server
from anvil import *

from ._anvil_designer import TenancyFormTemplate
from ... import gl, state


class TenancyForm(TenancyFormTemplate):
    """Add a tenant (opens the record) or edit a tenancy (save_tenancy). Closes with the reply ({tenancy}) or None."""

    def __init__(self, tenancy=None, property_id=None, **properties):
        super().__init__(**properties)
        t: dict = dict(tenancy) if tenancy else {"due_day": 1, "start_date": gl.today_iso_js()}
        self._t = t
        self._id = t.get("id")
        self.title_label.text = "Edit tenancy" if self._id else "Add a tenant"
        state.heading(self.title_label, 2)
        self.save_button.text = "Save" if self._id else "Open the record"
        self.lead.visible = not self._id
        self.prop_field.visible = not self._id
        self.unit_field.classes["full"] = bool(self._id)
        props = gl.active_props()
        self.prop_box.items = [(p["name"], p["id"]) for p in props]
        if property_id:
            self.prop_box.selected_value = property_id
        for b in (self.rent_box, self.due_box, self.deposit_box):
            state.set_control_attr(b, "inputmode", "decimal")
        state.set_control_attr(self.start_box, "type", "date")
        state.set_control_attr(self.end_box, "type", "date")
        state.set_control_attr(self.email_box, "type", "email")
        state.set_control_attr(self.email_box, "autocomplete", "off")
        state.set_control_attr(self.name_box, "maxlength", 80)
        state.set_control_attr(self.unit_box, "maxlength", 40)
        self.unit_box.text = str(t.get("unit") or "")
        self.name_box.text = str(t.get("tenant_name") or "")
        self.email_box.text = str(t.get("tenant_email") or "")
        self.rent_box.text = _s(t.get("rent"))
        self.due_box.text = _s(t.get("due_day"))
        self.start_box.text = str(t.get("start_date") or "")
        self.end_box.text = str(t.get("end_date") or "")
        self.deposit_box.text = _s(t.get("deposit") or "")

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        v = {"id": self._id, "unit": self.unit_box.text, "tenant_name": self.name_box.text, "tenant_email": self.email_box.text,
             "rent": self.rent_box.text, "due_day": self.due_box.text, "start_date": self.start_box.text,
             "end_date": self.end_box.text, "deposit": self.deposit_box.text,
             "property_id": self._t.get("property_id") if self._id else self.prop_box.selected_value}
        r = self._send("save_tenancy", v)
        if r:
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


def _s(v):
    if v is None or v == "":
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)
