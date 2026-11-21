import anvil.js
import anvil.server
from anvil import *
from anvil.js import window

from ._anvil_designer import TenantPageTemplate
from ... import gl, router, state
from ...Dialogs.ConditionReport import ConditionReport
from ...Dialogs.NewTask import NewTask
from ...Dialogs.ReportView import ReportView
from ...Dialogs.TaskView import TaskView


class TenantPage(TenantPageTemplate):
    """#t/<token>: the tenant's page, opened from the private link the landlord sends. No account; no app header or
    tab bar (Shell hides them on this page). Messages (sealed, permanent), repair requests (ask, follow the dates,
    confirm fixed), the lease and rent receipts, the landlord's badges, download the record. Checks every 30 s.
    Everything comes from the public token callables (tenant_view / post / request / confirm); the server decides
    what a tenant may see (no landlord costs, other properties or email)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.token = args[0] if args else ""
        self.top_arg = len(args) > 1 and args[1] == "top"
        self.name_key = "tname." + self.token[:12]
        self.D: dict = {}
        self.last_seq = 0
        self._todo_report = None
        self._renewal = None
        self.open_panel.add_event_handler("x-task", self._task)
        self.closed_panel.add_event_handler("x-task", self._task)
        self.thread_panel.add_event_handler("x-task-id", self._task_id)
        self.reports_panel.add_event_handler("x-report", self._report)
        state.set_control_attr(self.compose_box, "maxlength", 4000)
        state.set_control_attr(self.compose_box, "aria-label", "Your message")
        state.set_control_attr(self.name_box, "maxlength", 60)
        state.set_control_attr(self.name_box, "autocomplete", "name")
        nid = "tp-name-box"
        state.control(self.name_box).id = nid
        self.dom_nodes["name_lbl"].setAttribute("for", nid)
        self._timer = window.setInterval(anvil.js.report_exceptions(self._poll), 30000)
        self._load()

    def leave(self):
        window.clearInterval(self._timer)

    def _my_name(self):
        n = state.store_get(self.name_key, "") or ""
        return n or (gl.first_name(self.D["tenancy"]["tenant_name"]) if self.D else "")

    def _load(self, quiet=False):
        try:
            r = anvil.server.call_s("tenant_view", self.token, True) if quiet else anvil.server.call("tenant_view", self.token, True)
        except Exception as e:
            if quiet:
                return
            raise
        if not r or r.get("ok") is False:
            self.bad.visible = True
            self.main_part.visible = False
            self.dom_nodes["bad_text"].textContent = (r or {}).get("error") or "This link isn't valid."
            return
        self.bad.visible = False
        self.main_part.visible = True
        self._draw(r)

    def _draw(self, d):
        self.D = d
        gl.set_currency(d.get("currency"))
        t, p = d["tenancy"], d["property"]
        self.last_seq = d["entries"][-1]["seq"] if d["entries"] else 0
        dn = self.dom_nodes
        dn["top_title"].textContent = p["name"] + (" · " + t["unit"] if t.get("unit") else "")
        self.demo_banner.visible = bool(t.get("demo"))
        self.house.show(door=p.get("door"), glow=0.9, smoke=True, size=110)
        self.hello.text = "Hi " + gl.first_name(t["tenant_name"])
        state.heading(self.hello, 1)
        dn["landlord"].textContent = d["landlord_name"]
        self.badges_panel.items = [{"icon": i, "text": x} for i, x in gl.badges(d.get("stats"))]
        self._seal(d["seal"])
        to_confirm = [k for k in d["tasks"] if k["status"] == "done" and not k.get("confirmed_at")]
        self.confirm_banner.visible = bool(to_confirm)
        self._confirm_id = to_confirm[0]["id"] if to_confirm else None
        if to_confirm:
            dn["confirm_text"].textContent = gl.first_name(d["landlord_name"]) + ' marked "' + to_confirm[0]["title"] + '" as done.'
        self._thread(d["entries"], "tenant")
        self.compose_box.placeholder = "Write to " + gl.first_name(d["landlord_name"]) + "…"
        if not self.name_box.text:
            self.name_box.text = self._my_name()
        open_k = [k for k in d["tasks"] if k["status"] not in ("done", "declined")]
        closed = [k for k in d["tasks"] if k["status"] in ("done", "declined")]
        self.open_panel.items = open_k
        self.no_open.visible = not open_k
        self.closed_box.visible = bool(closed)
        self.closed_panel.items = closed
        dn["closed_sum"].textContent = state.plural(len(closed), "finished request")
        dn["f_rent"].textContent = gl.money(t["rent"], cents=True) + " / month"
        dn["f_due"].textContent = "Day %d of the month" % t["due_day"]
        dn["f_start"].textContent = gl.fmt_date(t.get("start_date"))
        dn["f_end_dt"].hidden = dn["f_end"].hidden = not t.get("end_date")
        dn["f_end"].textContent = gl.fmt_date(t.get("end_date"))
        dn["f_dep_dt"].hidden = dn["f_dep"].hidden = not t.get("deposit")
        dn["f_dep"].textContent = gl.money(t.get("deposit") or 0)
        dn["f_addr"].textContent = p.get("address") or p["name"]
        self.rec_box.visible = bool(d["rent_payments"])
        self.rec_panel.items = d["rent_payments"][:12]
        self._agreements(d.get("agreements") or {})

    def _agreements(self, ag):
        """Condition reports (list + "please check" banner) and the landlord's renewal offer (Accept / talk banner)."""
        reps = [dict(r, side="tenant") for r in ag.get("reports") or []]
        self.reports_panel.items = reps
        self.no_reports.visible = not reps
        todo = next((r for r in reps if r["author_kind"] != "tenant" and not r.get("answer")), None)
        self._todo_report = todo
        self.report_banner.visible = todo is not None
        if todo:
            self.dom_nodes["report_text"].textContent = "Please check the %s condition report from %s: agree, or say what isn't right." % (
                todo["label"].lower(), gl.first_name(todo["author_name"]))
        rn = ag.get("renewal")
        self._renewal = rn
        self.renew_banner.visible = bool(rn and rn["status"] == "sent")
        if rn and rn["status"] == "sent":
            terms = gl.money(rn["rent"], cents=True) + " a month from " + gl.fmt_date(rn["from"]) +                 ((", lease until " + gl.fmt_date(rn["until"])) if rn.get("until") else ", open-ended")
            self.dom_nodes["renew_text"].textContent = gl.first_name(self.D["landlord_name"]) + " offers to renew: " + terms +                 "." + ((' "' + rn["note"] + '"') if rn.get("note") else "")

    def _seal(self, seal):
        """The seal box: intact (count + fingerprint, Check again) or broken at entry N."""
        d = self.dom_nodes
        intact = bool(seal.get("intact"))
        d["seal"].className = "gl-seal" + ("" if intact else " broken")
        d["seal_icon"].className = "ic ic-" + ("seal" if intact else "info")
        if intact:
            d["seal_head"].textContent = "Sealed record:"
            d["seal_text"].textContent = state.plural(seal["count"], "entry", "entries") + ", nothing edited or deleted. Fingerprint"
            d["seal_code"].textContent = seal.get("head") or ""
            d["seal_code"].hidden = False
        else:
            d["seal_head"].textContent = "The seal is broken at entry #%s." % seal.get("broken_at")
            d["seal_text"].textContent = "Something in the record changed after it was written. Please tell us through Submit feedback."
            d["seal_code"].hidden = True
        self.verify_button.visible = intact

    def _thread(self, entries, side):
        items, last = [], ""
        for e in entries:
            day = gl.day_key(e["created"])
            items.append(dict(e, side=side, new_day=gl.fmt_date(e["created"], "full") if day != last else ""))
            last = day
        self.thread_panel.items = items

    def _poll(self):
        try:
            r = anvil.server.call_s("tenant_view", self.token, True)
        except Exception:
            return
        if not r or r.get("ok") is False:
            return
        seq = r["entries"][-1]["seq"] if r["entries"] else 0
        if seq == self.last_seq:
            return
        draft = self.compose_box.text
        self._draw(r)
        self.compose_box.text = draft

    @handle("name_box", "change")
    def name_box_change(self, **event_args):
        state.store_set(self.name_key, (self.name_box.text or "").strip())

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        body = (self.compose_box.text or "").strip()
        if not body:
            state.toast("Write a message first.", "error")
            return
        self.send_button.enabled = False
        try:
            r = state.call("tenant_post", self.token, self._my_name(), body)
        finally:
            self.send_button.enabled = True
        if r:
            self.compose_box.text = ""
            state.toast("Sent and sealed", "ok")
            self._load(quiet=True)

    @handle("verify_button", "click")
    def verify_button_click(self, **event_args):
        r = state.call("tenant_view", self.token, False)
        if r:
            s = r["seal"]
            state.toast("Checked: all %d entries are intact." % s["count"] if s["intact"] else "The seal is broken!", "ok" if s["intact"] else "error")
            self._seal(s)

    def _ask(self):
        def send(title, details, category, priority, photo_ids):
            return anvil.server.call("tenant_request", self.token, self._my_name(), title, details, category, priority,
                                     photo_ids)

        def tickets(items):
            return anvil.server.call("tenant_photo_tickets", self.token, items, self._my_name())
        if alert(NewTask(send=send, tickets=tickets if self.D.get("photos_on") else None),
                 buttons=[], role="app-dialog", large=True, dismissible=True):
            state.toast("Request sent. The date is on record.", "ok")
            self._load(quiet=True)

    @handle("ask_top", "click")
    def ask_top_click(self, **event_args):
        self._ask()

    @handle("ask_side", "click")
    def ask_side_click(self, **event_args):
        self._ask()

    @handle("download_button", "click")
    def download_button_click(self, **event_args):
        D = self.D
        gl.download_record("my-home-record-" + gl.today_iso_js() + ".txt",
                           {"property": D["property"], "unit": D["tenancy"].get("unit"), "tenant": D["tenancy"]["tenant_name"],
                            "landlord": D["landlord_name"], "seal": D["seal"], "entries": D["entries"], "tasks": D["tasks"]})

    def _open_task(self, tid):
        k = next((x for x in self.D["tasks"] if x["id"] == tid), None)
        if k and alert(TaskView(task=dict(k, where=""), tenant=True, token=self.token, name=self._my_name(),
                                photos_on=bool(self.D.get("photos_on"))),
                       buttons=[], role="app-dialog", large=True, dismissible=True):
            self._load(quiet=True)

    def _task(self, task, **event_args):
        self._open_task(task["id"])

    def _task_id(self, task_id, **event_args):
        self._open_task(task_id)

    def _report(self, report, **event_args):
        def answer(agree, note):
            return anvil.server.call("tenant_report_answer", self.token, report["seq"], agree, note, self._my_name())
        if alert(ReportView(report=report, side="tenant", answer=answer),
                 buttons=[], role="app-dialog", large=True, dismissible=True):
            state.toast("Your answer is sealed in the record", "ok")
            self._load(quiet=True)

    @handle("check_button", "click")
    def check_button_click(self, **event_args):
        if self._todo_report:
            self._report(self._todo_report)

    @handle("report_button", "click")
    def report_button_click(self, **event_args):
        reps = (self.D.get("agreements") or {}).get("reports") or []
        move_in = next((r for r in reps if r["kind"] == "move_in"), None)

        def send(kind, rooms, note):
            return anvil.server.call("tenant_report", self.token, kind, rooms, note, self._my_name())
        if alert(ConditionReport(send=send, kind="move_out" if move_in else "move_in", move_in_rooms=move_in["rooms"] if move_in else None,
                                 lead="Go room by room and note anything that isn't perfect. Your landlord can agree or say what they see."),
                 buttons=[], role="app-dialog", large=True, dismissible=True):
            state.toast("Report sealed in the record", "ok")
            self._load(quiet=True)

    def _renewal_answer(self, accept):
        rn = self._renewal
        if not rn:
            return
        note = ""
        if accept:
            if not confirm("Your landlord sees that you accepted, with today's date.", title="Accept the renewal offer?",
                           buttons=[("Cancel", False), ("Accept", True)], role="app-dialog"):
                return
        else:
            box = TextArea(placeholder="What would you like to talk about? (optional)")
            state.set_control_attr(box, "maxlength", 1000)
            state.set_control_attr(box, "aria-label", "What would you like to talk about?")
            if not alert(box, title="Talk about the offer", buttons=[("Cancel", False), ("Send", True)], role="app-dialog"):
                return
            note = box.text or ""
        if state.call("tenant_renewal_answer", self.token, rn["seq"], accept, note, self._my_name()):
            state.toast("Answer sealed in the record", "ok")
            self._load(quiet=True)

    @handle("accept_button", "click")
    def accept_button_click(self, **event_args):
        self._renewal_answer(True)

    @handle("talk_button", "click")
    def talk_button_click(self, **event_args):
        self._renewal_answer(False)

    @handle("answer_button", "click")
    def answer_button_click(self, **event_args):
        if self._confirm_id:
            self._open_task(self._confirm_id)
