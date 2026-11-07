import anvil.server
from anvil import *

from ._anvil_designer import EntryFormTemplate
from ... import gl, state


class EntryForm(EntryFormTemplate):
    """Add a ledger entry or edit one (add_entry / update_entry / delete_entry). Money out / Money in switches the
    categories (tax-claimable, capital, not claimable). Closes with the reply, "deleted" or None."""

    def __init__(self, entry=None, defaults=None, **properties):
        super().__init__(**properties)
        self._new = entry is None
        e = dict(entry) if entry else dict({"kind": "expense", "category": "repairs", "date": gl.today_iso_js()}, **(defaults or {}))
        self._e = e
        self.title_label.text = "Add to the ledger" if self._new else "Edit entry"
        state.heading(self.title_label, 2)
        self.delete_button.visible = not self._new
        props = [p for p in gl.data()["properties"] if not p.get("archived") or p["id"] == e.get("property_id")]
        self.prop_box.items = [(p["name"], p["id"]) for p in props]
        if e.get("property_id"):
            self.prop_box.selected_value = e["property_id"]
        state.set_control_attr(self.amount_box, "inputmode", "decimal")
        state.set_control_attr(self.date_box, "type", "date")
        state.set_control_attr(self.memo_box, "maxlength", 200)
        self.amount_box.text = _s(e.get("amount"))
        self.date_box.text = e.get("date") or ""
        self.memo_box.text = e.get("memo") or ""
        self._kind(e.get("kind") or "expense", e.get("category"))

    def _kind(self, kind, category=None):
        self._k = kind
        self.out_button.classes["on"] = kind == "expense"
        self.in_button.classes["on"] = kind == "income"
        cats = [c for c in gl.data()["categories"] if c["kind"] == kind]
        self.cat_box.items = [(c["label"] + (" · capital" if c.get("claim") == "capital" else " · not claimable" if c.get("claim") == "no" else ""), c["id"]) for c in cats]
        ids = [c["id"] for c in cats]
        self.cat_box.selected_value = category if category in ids else ("rent" if kind == "income" else "repairs") if (("rent" if kind == "income" else "repairs") in ids) else (ids[0] if ids else None)
        state.set_control_attr(self.cat_box, "aria-label", "Category")
        state.set_control_attr(self.prop_box, "aria-label", "Property")
        self._hint()

    def _hint(self):
        c = gl.category(self.cat_box.selected_value)
        self.cat_hint.text = c.get("hint") or ("Claimable this year." if c.get("claim") == "yes" else "")
        self.cat_hint.visible = bool(self.cat_hint.text)

    @handle("cat_box", "change")
    def cat_box_change(self, **event_args):
        self._hint()

    def out_click(self, event):
        self._kind("expense")

    def in_click(self, event):
        self._kind("income")

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        v = {"kind": self._k, "property_id": self.prop_box.selected_value, "category": self.cat_box.selected_value,
             "amount": self.amount_box.text, "date": self.date_box.text, "memo": self.memo_box.text}
        if self._e.get("tenancy_id"):
            v["tenancy_id"] = self._e["tenancy_id"]
        if self._e.get("rent_month"):
            v["rent_month"] = self._e["rent_month"]
        r = self._send("add_entry", v) if self._new else self._send("update_entry", self._e["id"], v)
        if r:
            self.raise_event("x-close-alert", value=r)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        e = self._e
        text = "The tenancy record will note that this rent record was removed." if e.get("category") == "rent" and e.get("tenancy_id") else ""
        if confirm(text, title="Delete this entry?", buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_entry", e["id"]):
                self.raise_event("x-close-alert", value="deleted")

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
