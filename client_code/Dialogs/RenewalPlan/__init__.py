from anvil import *

from ._anvil_designer import RenewalPlanTemplate
from ... import gl, state


class RenewalPlan(RenewalPlanTemplate):
    """Plan a lease renewal and send the offer (send_renewal): rent change slider (−5%..+10%) synced with the new rent,
    start and end dates, a note, and the keep-a-good-tenant maths (the increase over a year vs one empty month).
    The offer is sealed into the record, which is the proof of when the notice was given.
    tenancy = the tenancy dict, send(rent, start, until, note) = the server call. Closes with the reply or None."""

    def __init__(self, tenancy=None, send=None, notice_days=60, **properties):
        super().__init__(**properties)
        t = tenancy or {}
        self._send_fn = send or _no_send
        self.old = float(t.get("rent") or 0)
        state.heading(self.title_label, 2)
        end = (t.get("end_date") or "")[:10]
        today = gl.today_iso_js()
        start = gl.add_days(end, 1) if end and end >= today else gl.add_months(today[:8] + "01", 2)
        self.start_box.text = start
        self.until_box.text = gl.add_days(gl.add_months(start, 12), -1)
        for box in (self.start_box, self.until_box):
            state.set_control_attr(box, "type", "date")
        state.set_control_attr(self.rent_box, "inputmode", "decimal")
        state.set_control_attr(self.note_box, "maxlength", 600)
        lead = gl.first_name(t.get("tenant_name")) + " pays " + gl.money(self.old) + " a month"
        lead += (", lease until " + gl.fmt_date(end) + ".") if end else ", open-ended lease."
        self.dom_nodes["lead"].textContent = lead + " Choose the new terms; your tenant accepts or asks to talk in the record."
        if end:
            by = gl.add_days(end, -notice_days)
            left = gl.days_between(today, by)
            self.dom_nodes["notice"].textContent = (
                ("Many leases and local rules ask for about %d days' notice: send it by %s (%s)." %
                 (notice_days, gl.fmt_date(by), "today" if left == 0 else ("in %d days" % left) if left > 0 else "%d days ago" % -left))
                + " Check your lease and local rules for the exact notice and any limit on increases.")
        else:
            self.dom_nodes["notice"].textContent = "Check your lease and local rules for the notice period and any limit on increases."
        self.pct_slider.setup(-5, 10, 0.5, 3, "−5%", "+10%")
        self.pct_slider.add_event_handler("change", self._slid)
        self._slid()

    def _slid(self, **event_args):
        new = round(self.old * (1 + self.pct_slider.value / 100), 0)
        self.rent_box.text = ("%.0f" % new) if self.old else ""
        self._update()

    @handle("rent_box", "change")
    def rent_box_change(self, **event_args):
        self._update(from_box=True)

    def _update(self, from_box=False):
        new = gl.num(self.rent_box.text)
        pct = ((new - self.old) / self.old * 100) if self.old else 0
        if from_box and self.old:
            self.pct_slider.value = max(-5, min(10, pct))
        self.pct_slider.shown = ("+" if pct > 0 else "") + ("%.1f%%" % pct)
        diff = new - self.old
        d = self.dom_nodes
        d["m_month"].textContent = gl.signed(diff)
        d["m_year"].textContent = gl.signed(diff * 12)
        d["m_vacant"].textContent = gl.money(new)
        if diff > 0:
            months = new / diff
            d["say"].textContent = ("If a higher rent made them leave, one empty month would cost about %s months of this "
                                    "increase%s. Keeping a good tenant is often worth more than the last few dollars." %
                                    ("%.0f" % months, ", before cleaning and listing costs" if months < 60 else ""))
        elif diff < 0:
            d["say"].textContent = "A lower rent: a kind way to keep a great tenant."
        else:
            d["say"].textContent = "Same rent: renew the lease as it is."

    def _fail(self, message):
        self.error_label.text = message
        self.error_label.visible = True

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        if gl.num(self.rent_box.text) <= 0:
            self._fail("Enter the new monthly rent.")
            return
        if not self.start_box.text:
            self._fail("Choose the date the new terms start.")
            return
        self.error_label.visible = False
        self.send_button.enabled = False
        try:
            r = self._send_fn(self.rent_box.text, self.start_box.text, self.until_box.text or None, self.note_box.text or "")
        finally:
            self.send_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self._fail(r.get("error") or "That didn't work.")
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)


def _no_send(rent, start, until, note):
    return {"ok": False, "error": "Nothing to send to."}
