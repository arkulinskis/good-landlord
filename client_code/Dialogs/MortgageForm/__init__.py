import anvil.server
from anvil import *

from ._anvil_designer import MortgageFormTemplate
from ... import gl, state


class MortgageForm(MortgageFormTemplate):
    """Add or edit a mortgage (save_mortgage / delete_mortgage). Closes with the reply, "deleted" or None."""

    def __init__(self, mortgage=None, property_id=None, **properties):
        super().__init__(**properties)
        d = gl.data() or {}
        mo = dict(mortgage) if mortgage else {"frequency": "monthly", "compounding": (d.get("prefs") or {}).get("compounding") or "semiannual",
                                              "amort_years": 25, "term_years": 5}
        self._id = mo.get("id")
        self._prop_id = property_id or mo.get("property_id")
        prop = gl.prop(self._prop_id) or {}
        if not self._id and not mo.get("amount") and prop.get("purchase_price"):
            mo["amount"] = max(0, prop["purchase_price"] - (prop.get("down_payment") or 0))
        self.title_label.text = "Edit mortgage" if self._id else "Add a mortgage"
        state.heading(self.title_label, 2)
        self.lead_label.text = (prop.get("name") or "") + ". Payments are worked out from these numbers, so you don't add them to the ledger."
        self.delete_button.visible = bool(self._id)
        self.freq_box.items = [(label, key) for key, label in gl.FREQ]
        self.freq_box.selected_value = mo.get("frequency") or "monthly"
        self.comp_box.items = [(label, key) for key, label in gl.COMPOUNDING]
        self.comp_box.selected_value = mo.get("compounding") or "semiannual"
        state.set_control_attr(self.freq_box, "aria-label", "Payments")
        state.set_control_attr(self.comp_box, "aria-label", "Interest compounding")
        for b in (self.amount_box, self.rate_box, self.amort_box, self.term_box):
            state.set_control_attr(b, "inputmode", "decimal")
        state.set_control_attr(self.start_box, "type", "date")
        self.lender_box.text = mo.get("lender") or ""
        self.amount_box.text = _s(mo.get("amount"))
        self.rate_box.text = _s(mo.get("rate"))
        self.start_box.text = mo.get("start_date") or prop.get("purchase_date") or ""
        self.amort_box.text = _s(mo.get("amort_years"))
        self.term_box.text = _s(mo.get("term_years"))

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        v = {"id": self._id, "property_id": self._prop_id, "lender": self.lender_box.text, "amount": self.amount_box.text,
             "rate": self.rate_box.text, "start_date": self.start_box.text, "frequency": self.freq_box.selected_value,
             "amort_years": self.amort_box.text, "term_years": self.term_box.text, "compounding": self.comp_box.selected_value}
        r = self._send("save_mortgage", v)
        if r:
            self.raise_event("x-close-alert", value=r)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("", title="Delete this mortgage?", buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_mortgage", self._id):
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
