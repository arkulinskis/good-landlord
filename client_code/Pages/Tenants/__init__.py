from anvil import *

from ._anvil_designer import TenantsTemplate
from ... import gl, router, state
from ...Dialogs.TaskView import TaskView
from ...Dialogs.TenancyForm import TenancyForm

COLS = [("requested", "New"), ("acknowledged", "Seen"), ("scheduled", "Scheduled"), ("in_progress", "In progress"), ("done", "Done (30 days)")]


class Tenants(TenantsTemplate):
    """#tenants (every tenancy: unread, open requests, copy the private link, open the record) and #tenants/requests
    (a board of every repair request by status; tap one to move it along)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = "requests" if args and args[0] == "requests" else "list"
        self.board_panel.add_event_handler("x-task", self._task)
        self._draw()

    def _draw(self):
        d = gl.load()
        tab = self.tab
        self.tab_list.classes["on"] = tab == "list"
        self.tab_requests.classes["on"] = tab == "requests"
        open_n = len([k for k in d["tasks"] if k["status"] not in ("done", "declined")])
        unread = sum(t.get("unread") or 0 for t in d["tenancies"])
        self.dom_nodes["unread"].textContent = ("%d new" % unread) if unread else ""
        self.dom_nodes["unread"].hidden = not unread
        self.dom_nodes["open"].textContent = ("%d open" % open_n) if open_n else ""
        self.dom_nodes["open"].hidden = not open_n
        self.list_part.visible = tab == "list"
        self.requests_part.visible = tab == "requests"
        if tab == "list":
            groups = []
            for p in d["properties"]:
                ts = [t for t in d["tenancies"] if t["property_id"] == p["id"]]
                if ts:
                    ts.sort(key=lambda t: 1 if t["status"] == "ended" else 0)
                    groups.append({"p": p, "tenancies": ts})
            self.groups_panel.items = groups
            self.no_tenants.visible = not d["tenancies"]
            self.add_tenant_empty.visible = bool(d["properties"])
            self.first_prop.visible = not d["properties"]
        else:
            b = gl.badges(d.get("stats"))
            self.badges_panel.items = [{"icon": i, "text": t} for i, t in b]
            self.no_badges.visible = not b
            month_ago = gl.iso_days_ago(31)
            cols = []
            for key, title in COLS:
                ks = [dict(k, show_where=True) for k in d["tasks"] if k["status"] == key and (key != "done" or (k.get("done_at") or "")[:10] > month_ago)]
                if key == "requested":
                    ks.sort(key=lambda k: 0 if k.get("priority") == "urgent" else 1)
                cols.append({"title": title, "tasks": ks})
            self.board_panel.items = cols

    def _add(self):
        props = gl.active_props()
        if not props:
            state.toast("Add a property first.")
            return
        r = alert(TenancyForm(property_id=props[0]["id"]), buttons=[], role="app-dialog", large=True, dismissible=True)
        if r:
            state.toast("Record opened", "ok")
            router.go("tenancy", r["tenancy"]["id"], "share")

    @handle("add_tenant", "click")
    def add_tenant_click(self, **event_args):
        self._add()

    @handle("add_tenant_empty", "click")
    def add_tenant_empty_click(self, **event_args):
        self._add()

    def _task(self, task, **event_args):
        k = next((x for x in gl.data()["tasks"] if x["id"] == task["id"]), None)
        if k and alert(TaskView(task=k, landlord=True), buttons=[], role="app-dialog", large=True, dismissible=True):
            self._draw()
