import anvil.js
import anvil.server
from anvil import *
from anvil.js import window

from ._anvil_designer import TenancyTemplate
from ... import gl, router, state
from ...Dialogs.NewTask import NewTask
from ...Dialogs.ShareLink import ShareLink
from ...Dialogs.TaskView import TaskView
from ...Dialogs.TenancyForm import TenancyForm


class Tenancy(TenancyTemplate):
    """#tenancy/<id>[/share] (Operate): the landlord's side of one permanent record. The sealed thread (messages + every
    task move with its date), the composer, requests (new task, move along), lease facts, rent received, the tenant's
    private link (copy, email, reset), download, edit, end/reopen, delete-if-unused. Checks for new entries every 30 s.
    Nothing here edits or deletes a record entry: the server has no such call (Record.py appends only)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tid = args[0] if args else ""
        self.share_first = len(args) > 1 and args[1] == "share"
        self.D: dict = {}
        self.last_seq = 0
        self.open_panel.add_event_handler("x-task", self._task)
        self.closed_panel.add_event_handler("x-task", self._task)
        self.thread_panel.add_event_handler("x-task-id", self._task_id)
        state.set_control_attr(self.compose_box, "maxlength", 4000)
        state.set_control_attr(self.compose_box, "aria-label", "Your message")
        anvil.js.get_dom_node(self.compose_box).addEventListener("keydown", anvil.js.report_exceptions(self._keys))
        self._timer = window.setInterval(anvil.js.report_exceptions(self._poll), 30000)
        self._load()

    def leave(self):
        window.clearInterval(self._timer)

    def after_open(self):
        if self.D:
            box = self.dom_nodes["thread_box"]
            box.scrollTop = box.scrollHeight
        if self.share_first and self.D:
            self.share_first = False
            window.setTimeout(anvil.js.report_exceptions(lambda: self.share_button_click()), 50)

    def _load(self, quiet=False):
        r = anvil.server.call_s("get_tenancy", self.tid) if quiet else anvil.server.call("get_tenancy", self.tid)
        if not r or r.get("ok") is False:
            self.missing.visible = True
            self.main_part.visible = False
            self.dom_nodes["missing_text"].textContent = (r or {}).get("error") or "It isn't yours, or it was deleted."
            return
        self.missing.visible = False
        self.main_part.visible = True
        self._draw(r)

    def _draw(self, d):
        self.D = d
        gl.set_currency((d.get("prefs") or {}).get("currency"))
        t = d["tenancy"]
        self.last_seq = d["entries"][-1]["seq"] if d["entries"] else 0
        self.title.text = t["tenant_name"]
        state.heading(self.title, 1)
        self.dom_nodes["sub"].textContent = d["property"]["name"] + (" · " + t["unit"] if t.get("unit") else "") + (" · sample" if t.get("demo") else "")
        self.dom_nodes["ended"].hidden = t["status"] != "ended"
        self._seal(d["seal"])
        self._thread(d["entries"], "landlord")
        self.compose_box.placeholder = "Write to " + gl.first_name(t["tenant_name"]) + "… (kept for good, can't be deleted)"
        open_k = [k for k in d["tasks"] if k["status"] not in ("done", "declined")]
        closed = [k for k in d["tasks"] if k["status"] in ("done", "declined")]
        self.open_panel.items = open_k
        self.no_open.visible = not open_k
        self.closed_box.visible = bool(closed)
        self.closed_panel.items = closed
        self.dom_nodes["closed_sum"].textContent = state.plural(len(closed), "finished request")
        dn = self.dom_nodes
        dn["f_rent"].textContent = gl.money(t["rent"], cents=True) + " / month"
        dn["f_due"].textContent = "Day %d" % t["due_day"]
        dn["f_start"].textContent = gl.fmt_date(t.get("start_date"))
        dn["f_end"].textContent = gl.fmt_date(t["end_date"]) if t.get("end_date") else "Open-ended"
        dn["f_dep_dt"].hidden = dn["f_dep"].hidden = not t.get("deposit")
        dn["f_dep"].textContent = gl.money(t.get("deposit") or 0)
        dn["f_email_dt"].hidden = dn["f_email"].hidden = not t.get("tenant_email")
        dn["f_email"].textContent = t.get("tenant_email") or ""
        dn["f_visit"].textContent = gl.ago(t["tenant_last_visit"]) if t.get("tenant_last_visit") else "Not yet"
        self.rent_box.visible = bool(d["rent_payments"])
        self.rent_panel.items = d["rent_payments"][:12]
        self.end_button.visible = t["status"] != "ended"
        self.reopen_button.visible = t["status"] == "ended"
        self.delete_button.visible = (t.get("entries") or 0) <= 1 and not t.get("tenant_last_visit")
        window.setTimeout(anvil.js.report_exceptions(self._scroll_down), 30)

    def _scroll_down(self):
        box = self.dom_nodes["thread_box"]
        box.scrollTop = box.scrollHeight

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
            r = anvil.server.call_s("get_tenancy", self.tid)
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

    def _keys(self, event):
        if event.key == "Enter" and (event.ctrlKey or event.metaKey):
            event.preventDefault()
            self.send_button_click()

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        body = (self.compose_box.text or "").strip()
        if not body:
            state.toast("Write a message first.", "error")
            return
        self.send_button.enabled = False
        try:
            r = state.call("landlord_post", self.tid, body)
        finally:
            self.send_button.enabled = True
        if r:
            self.compose_box.text = ""
            self._load(quiet=True)

    @handle("verify_button", "click")
    def verify_button_click(self, **event_args):
        r = state.call("verify_record", self.tid)
        if r:
            s = r["seal"]
            state.toast("Checked: all %d entries are intact." % s["count"] if s["intact"] else "The seal is broken!", "ok" if s["intact"] else "error")
            self.D["seal"] = s
            self._seal(s)

    @handle("share_button", "click")
    def share_button_click(self, **event_args):
        r = alert(ShareLink(tenancy=self.D["tenancy"], property_name=self.D["property"]["name"]), buttons=[], role="app-dialog", large=True, dismissible=True)
        if r == "reset":
            self._load(quiet=True)
            self.share_button_click()

    @handle("download_button", "click")
    def download_button_click(self, **event_args):
        D = self.D
        t = D["tenancy"]
        safe = "".join(ch if ch.isalnum() else "-" for ch in t["tenant_name"].lower())
        while "--" in safe:
            safe = safe.replace("--", "-")
        gl.download_record("record-" + safe.strip("-") + "-" + gl.today_iso_js() + ".txt",
                           {"property": D["property"], "unit": t.get("unit"), "tenant": t["tenant_name"], "landlord": D["landlord_name"],
                            "seal": D["seal"], "entries": D["entries"], "tasks": D["tasks"]})

    @handle("new_task", "click")
    def new_task_click(self, **event_args):
        def send(title, details, category, priority):
            return anvil.server.call("landlord_new_task", self.tid, title, details, category, priority)
        r = alert(NewTask(send=send, title="Add a task", lead="For work you plan yourself (inspections, servicing). Your tenant sees it in their record.",
                          ok="Add task"), buttons=[], role="app-dialog", large=True, dismissible=True)
        if r:
            state.toast("Task added", "ok")
            self._load(quiet=True)

    def _open_task(self, tid):
        k = next((x for x in self.D["tasks"] if x["id"] == tid), None)
        if k and alert(TaskView(task=dict(k, where=""), landlord=True), buttons=[], role="app-dialog", large=True, dismissible=True):
            self._load(quiet=True)

    def _task(self, task, **event_args):
        self._open_task(task["id"])

    def _task_id(self, task_id, **event_args):
        self._open_task(task_id)

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        gl.load()
        if alert(TenancyForm(tenancy=self.D["tenancy"]), buttons=[], role="app-dialog", large=True, dismissible=True):
            state.toast("Saved", "ok")
            self._load(quiet=True)

    @handle("end_button", "click")
    def end_button_click(self, **event_args):
        if confirm("It leaves the rent roll. The record stays readable for both of you, and the tenant can still write in it.",
                   title="End this tenancy?", buttons=[("Cancel", False), ("End tenancy", True)], role="app-dialog"):
            if state.call("end_tenancy", self.tid, None):
                self._load(quiet=True)

    @handle("reopen_button", "click")
    def reopen_button_click(self, **event_args):
        if state.call("reopen_tenancy", self.tid):
            self._load(quiet=True)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("Only possible because nobody has used it yet.", title="Delete this record?",
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_tenancy", self.tid):
                router.go("tenants")
