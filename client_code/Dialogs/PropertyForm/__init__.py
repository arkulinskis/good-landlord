import anvil.server
from anvil import *

from ._anvil_designer import PropertyFormTemplate
from ... import gl, state

NUMS = ("units_box", "price_box", "down_box", "closing_box", "impr_box", "value_box", "appr_box", "sell_box")


class PropertyForm(PropertyFormTemplate):
    """Add or edit a property (save_property). Closes with the reply ({property}) or None."""

    def __init__(self, prop=None, **properties):
        super().__init__(**properties)
        p: dict = dict(prop) if prop else {"kind": "house", "units": 1, "appreciation": 3, "selling_pct": 5, "door": "red"}
        self._id = p.get("id")
        self.title_label.text = ("Edit " + str(p["name"])) if self._id else "Add a property"
        state.heading(self.title_label, 2)
        self.save_button.text = "Save" if self._id else "Add property"
        self.kind_box.items = [(label, key) for key, label in gl.KINDS]
        self.kind_box.selected_value = p.get("kind") or "house"
        state.set_control_attr(self.kind_box, "aria-label", "Type")
        for name in NUMS:
            state.set_control_attr(getattr(self, name), "inputmode", "decimal")
        state.set_control_attr(self.date_box, "type", "date")
        state.set_control_attr(self.name_box, "maxlength", 80)
        state.set_control_attr(self.address_box, "maxlength", 160)
        state.set_control_attr(self.notes_box, "maxlength", 2000)
        self.name_box.text = str(p.get("name") or "")
        self.address_box.text = str(p.get("address") or "")
        self.units_box.text = _s(p.get("units") or 1)
        self.price_box.text = _s(p.get("purchase_price"))
        self.date_box.text = str(p.get("purchase_date") or "")
        self.down_box.text = _s(p.get("down_payment"))
        self.closing_box.text = _s(p.get("closing_costs"))
        self.impr_box.text = _s(p.get("improvements"))
        self.value_box.text = _s(p.get("current_value"))
        self.appr_box.text = _s(p.get("appreciation"))
        self.sell_box.text = _s(p.get("selling_pct"))
        self.notes_box.text = str(p.get("notes") or "")
        n = self.dom_nodes
        self._doors = {"red": n["door_red"], "honey": n["door_honey"], "sage": n["door_sage"], "blue": n["door_blue"],
                       "plum": n["door_plum"], "walnut": n["door_walnut"]}
        self._doors.get(str(p.get("door") or "red"), n["door_red"]).checked = True

    def _door(self):
        for key, node in self._doors.items():
            if node.checked:
                return key
        return "red"

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        v = {"id": self._id, "name": self.name_box.text, "address": self.address_box.text, "kind": self.kind_box.selected_value,
             "units": self.units_box.text, "purchase_price": self.price_box.text, "purchase_date": self.date_box.text,
             "down_payment": self.down_box.text, "closing_costs": self.closing_box.text, "improvements": self.impr_box.text,
             "current_value": self.value_box.text, "appreciation": self.appr_box.text, "selling_pct": self.sell_box.text,
             "door": self._door(), "notes": self.notes_box.text}
        if len((v["name"] or "").strip()) < 2:
            self._fail("Give the property a name (at least 2 characters).")
            return
        r = self._send("save_property", v)
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
