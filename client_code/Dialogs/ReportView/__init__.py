from anvil import *

from ._anvil_designer import ReportViewTemplate
from ... import gl, state
from ...Items.ReportRow import status_of


class ReportView(ReportViewTemplate):
    """One condition report: counts, changes since move-in (move-out reports), every room, the answer.
    The side that didn't write it answers here once: I agree, or I don't agree + what isn't right (sealed).
    report = a report dict (Agreements.summary), side = 'landlord' | 'tenant', answer(agree, note) = the server call.
    Closes with True when an answer was sealed, else None."""

    def __init__(self, report=None, side="landlord", answer=None, **properties):
        super().__init__(**properties)
        r = report or {}
        self._answer_fn = answer or _no_answer
        d = self.dom_nodes
        self.title_label.text = r.get("label", "") + " condition report"
        state.heading(self.title_label, 2)
        mine = r.get("author_kind") == side
        d["sub"].textContent = (("Written by you" if mine else "Written by " + (r.get("author_name") or "")) + " on "
                                + gl.fmt_date(r.get("created")) + " · entry #%s, sealed" % r.get("seq"))
        c = r.get("counts") or {}
        d["counts"].textContent = " · ".join("%d %s" % (c[k], k.lower()) for k in ("Good", "Worn", "Damaged", "Missing") if c.get(k))
        changes = r.get("changes") or []
        self.changes_box.visible = r.get("kind") == "move_out" and r.get("compared_to") is not None
        self.changes_panel.items = changes
        if self.changes_box.visible:
            d["changes_h"].textContent = (("Changes since the move-in report #%s" % r["compared_to"]) if changes
                                          else "No room is worse than in the move-in report #%s" % r["compared_to"])
        self.rooms_panel.items = r.get("rooms") or []
        d["note"].textContent = ("Note: " + r["note"]) if r.get("note") else ""
        d["note"].hidden = not r.get("note")
        a = r.get("answer")
        d["answer"].hidden = (not a) and (not mine)
        if a:
            who = "You" if a["author_kind"] == side else a["by"]
            d["answer"].className = "gl-rv-answer " + ("good" if a["agree"] else "bad")
            d["answer_icon"].className = "ic ic-" + ("check" if a["agree"] else "chat")
            d["answer_text"].textContent = (who + (" agreed" if a["agree"] else " didn't agree") + " on "
                                            + gl.fmt_date(a["created"]) + ((": " + a["note"]) if a.get("note") else "."))
        elif mine:
            d["answer"].className = "gl-rv-answer"
            d["answer_icon"].className = "ic ic-clock"
            d["answer_text"].textContent = status_of(r, side)[0] + " from the other side."
        self.ask_box.visible = (not a) and (not mine) and answer is not None
        self.why_field.visible = False
        state.set_control_attr(self.why_box, "maxlength", 1000)

    def _send(self, agree):
        note = (self.why_box.text or "").strip()
        self.error_label.visible = False
        self.agree_button.enabled = False
        self.disagree_button.enabled = False
        try:
            r = self._answer_fn(agree, note)
        finally:
            self.agree_button.enabled = True
            self.disagree_button.enabled = True
        if isinstance(r, dict) and r.get("ok") is False:
            self.error_label.text = r.get("error") or "That didn't work."
            self.error_label.visible = True
            return
        self.raise_event("x-close-alert", value=True)

    @handle("agree_button", "click")
    def agree_button_click(self, **event_args):
        self._send(True)

    @handle("disagree_button", "click")
    def disagree_button_click(self, **event_args):
        if not self.why_field.visible:
            self.why_field.visible = True
            self.disagree_button.text = "Send: I don't agree"
            state.focus(self.why_box)
            return
        if not (self.why_box.text or "").strip():
            self.error_label.text = "Say what isn't right, so it's on record."
            self.error_label.visible = True
            return
        self._send(False)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)


def _no_answer(agree, note):
    return {"ok": False, "error": "Nothing to send to."}
