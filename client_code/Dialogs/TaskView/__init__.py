import anvil.server
from anvil import *

from ._anvil_designer import TaskViewTemplate
from ... import gl, state

ORDER = ["requested", "acknowledged", "scheduled", "in_progress", "done"]
MOVES = ["acknowledged", "scheduled", "in_progress", "done", "declined", "requested"]


class TaskView(TaskViewTemplate):
    """A repair request: every date (asked, seen, scheduled, started, done, confirmed). The landlord moves it along
    (set_task_status; a note, a date for Schedule, a cost for Done); the tenant confirms a done job (tenant_confirm).
    Closes with True when something changed."""

    def __init__(self, task=None, landlord=False, tenant=False, token=None, name=None, **properties):
        super().__init__(**properties)
        k: dict = dict(task or {})
        self._k, self._token, self._name, self._to = k, token, name, None
        d = self.dom_nodes
        d["chip"].className = "gl-status gl-st-" + k["status"]
        d["chip"].textContent = gl.STATUS_LABEL.get(k["status"], k["status"])
        d["urgent"].hidden = k.get("priority") != "urgent"
        d["num"].textContent = "#%d · %s" % (k.get("number") or 0, gl.TASK_CAT_LABEL.get(k.get("category"), ""))
        self.title_label.text = k["title"]
        state.heading(self.title_label, 2)
        d["where"].textContent = k.get("where") or ""
        d["where"].hidden = not k.get("where")
        d["details"].textContent = k.get("details") or ""
        d["details"].hidden = not k.get("details")
        idx = ORDER.index(k["status"]) if k["status"] in ORDER else -1
        for i, el in enumerate([d["s0"], d["s1"], d["s2"], d["s3"], d["s4"]]):
            if idx >= i:
                el.classList.add("on")
        d["t_asked"].textContent = _dt(k.get("requested_at"))
        d["t_by"].textContent = "by " + (k.get("requested_name") or "")
        d["t_seen"].textContent = _dt(k.get("acknowledged_at"))
        d["t_sched"].textContent = gl.fmt_date(k["scheduled_for"], "wdmy") if k.get("scheduled_for") else "·"
        d["t_started"].textContent = _dt(k.get("started_at"))
        d["t_done"].textContent = _dt(k.get("done_at"))
        d["t_took"].textContent = "(%s after asking)" % gl.days(k["days_open"]) if k.get("done_at") and k.get("days_open") is not None else ""
        d["t_conf"].textContent = _dt(k.get("confirmed_at"))
        show_cost = bool(landlord and k.get("cost"))
        d["cost_dt"].hidden = not show_cost
        d["t_cost"].hidden = not show_cost
        d["t_cost"].textContent = gl.money(k.get("cost") or 0, cents=True)
        self.moves.visible = bool(landlord)
        self.extra.visible = False
        closed = k["status"] in ("done", "declined")
        for m in MOVES:
            b = getattr(self, "m_" + m)
            b.visible = (m == "requested" and closed) or (m != "requested" and (m != k["status"] or m == "scheduled"))
            b.set_event_handler("click", self._pick)
            b.tag = m
        self.confirm_box.visible = bool(tenant and k["status"] == "done" and not k.get("confirmed_at"))
        state.set_control_attr(self.when_box, "type", "date")
        state.set_control_attr(self.cost_box, "inputmode", "decimal")
        state.set_control_attr(self.note_box, "maxlength", 1000)
        state.set_control_attr(self.tnote_box, "maxlength", 1000)
        state.set_control_attr(self.tnote_box, "aria-label", "Anything to add")
        self.when_box.text = k.get("scheduled_for") or gl.vm("plusDaysIso", 2)
        self.cost_box.text = str(k.get("cost") or "")

    def _pick(self, sender, **event_args):
        to = sender.tag
        self._to = to
        for m in MOVES:
            b = getattr(self, "m_" + m)
            b.classes["picked"] = m == to
            state.set_control_attr(b, "aria-pressed", "true" if m == to else "false")
        self.extra.visible = True
        self.when_field.visible = to == "scheduled"
        self.cost_field.visible = to == "done"
        self.dom_nodes["note_req"].textContent = "(required: why?)" if to == "declined" else "(optional)"
        self.go_move.text = "Move to " + gl.STATUS_LABEL.get(to, to)

    @handle("cancel_move", "click")
    def cancel_move_click(self, **event_args):
        self.extra.visible = False
        self._to = None

    @handle("go_move", "click")
    def go_move_click(self, **event_args):
        to = self._to
        if not to:
            return
        r = state.call("set_task_status", self._k["id"], to, self.when_box.text if to == "scheduled" else None,
                       self.note_box.text, self.cost_box.text if to == "done" else None)
        if r:
            state.toast("Moved to " + gl.STATUS_LABEL.get(to, to), "ok")
            self.raise_event("x-close-alert", value=True)

    def _confirm(self, fixed):
        r = state.call("tenant_confirm", self._token, self._k["id"], fixed, self._name or None, self.tnote_box.text)
        if r:
            state.toast("Thanks! Noted in the record." if fixed else "Reopened. Your landlord will see it.", "ok")
            self.raise_event("x-close-alert", value=True)

    @handle("fixed_button", "click")
    def fixed_button_click(self, **event_args):
        self._confirm(True)

    @handle("notyet_button", "click")
    def notyet_button_click(self, **event_args):
        self._confirm(False)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)


def _dt(iso):
    return gl.fmt_datetime(iso) if iso else "·"
