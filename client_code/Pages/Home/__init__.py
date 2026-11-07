from anvil import *

from ._anvil_designer import HomeTemplate
from ... import gl, router, state
from ...Dialogs.EntryForm import EntryForm
from ...Dialogs.PropertyForm import PropertyForm


def hello(name):
    h = gl.hour_now()
    part = "Good evening" if h < 5 else "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
    return part + ", " + (gl.first_name(name) or "there")


def attention(d):
    """New requests, unread messages, rent not recorded, renewals soon, visits this week."""
    items, today = [], gl.today()
    ym, day = today[:7], int(today[8:10])
    for k in d["tasks"]:
        if k["status"] == "requested":
            urgent = k.get("priority") == "urgent"
            items.append({"go": router.href("tenancy", k["tenancy_id"]), "icon": "wrench", "cls": "bad" if urgent else "",
                          "t": ("Urgent: " if urgent else "New request: ") + k["title"], "s": k["where"] + " · asked " + gl.ago(k["requested_at"])})
    for t in d["tenancies"]:
        if t.get("unread"):
            lm = t.get("last_message")
            s = ('"' + lm["body"][:70] + ("…" if len(lm["body"]) > 70 else "") + '"') if lm else ""
            items.append({"go": router.href("tenancy", t["id"]), "icon": "chat", "cls": "",
                          "t": state.plural(t["unread"], "new message") + " from " + t["tenant_name"], "s": s})
    for t in d["tenancies"]:
        if t["status"] != "active":
            continue
        paid = any(e.get("tenancy_id") == t["id"] and e["category"] == "rent" and e.get("rent_month") == ym for e in d["ledger"])
        if paid or day < t["due_day"]:
            continue
        late = day - t["due_day"]
        items.append({"go": "#money/rent", "icon": "receipt", "cls": "bad" if late > 5 else "warn", "t": "Rent not recorded: " + t["tenant_name"],
                      "s": gl.money(t["rent"]) + " was due " + ("today" if late == 0 else state.plural(late, "day") + " ago") + " · " + t["property_name"]})
    for r in gl.vm("renewalsVM"):
        p = gl.prop(r["property_id"])
        items.append({"go": router.href("deal", r["property_id"], "mortgage"), "icon": "percent", "cls": "warn" if r["days"] < 45 else "",
                      "t": "Mortgage renews in " + state.plural(r["days"], "day"), "s": (p["name"] + " · " if p else "") + 'try the "rate at renewal" slider'})
    for k in d["tasks"]:
        if k["status"] == "scheduled" and k.get("scheduled_for"):
            days = gl.days_between(today, k["scheduled_for"][:10])
            if 0 <= days <= 7:
                items.append({"go": router.href("tenancy", k["tenancy_id"]), "icon": "calendar", "cls": "",
                              "t": k["title"] + (" today" if days == 0 else " tomorrow" if days == 1 else " in %d days" % days), "s": k["where"]})
    return items


class Home(HomeTemplate):
    """#home (Operate): the landlord's street of houses (windows glow with cash flow), the four numbers that matter,
    what needs attention, property cards, response badges. Empty state: add a property or load the sample."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self._draw()

    def _draw(self):
        d = gl.load()
        me = state.me() or {}
        props = gl.active_props()
        empty = not props and not d["properties"]
        self.empty_part.visible = empty
        self.main_part.visible = not empty
        if empty:
            self.hello_empty.text = hello(me.get("name"))
            state.heading(self.hello_empty, 1)
            return
        self.hello.text = hello(me.get("name"))
        state.heading(self.hello, 1)
        self.date_line.text = str(gl.window_today_long())
        self.sample_banner.visible = bool(d.get("has_sample"))
        ms = [gl.metrics(p["id"]) for p in props]
        self.street_panel.items = [{"id": p["id"], "name": p["name"], "door": p["door"], "kind": p["kind"], "glow": m["glow"],
                                    "smoke": m["cashMonthly"] > 0} for p, m in zip(props, ms)]
        ym = gl.today()[:7]
        expected = sum(t["rent"] for t in d["tenancies"] if t["status"] == "active")
        collected = sum(e["amount"] for e in d["ledger"] if e["category"] == "rent" and e.get("rent_month") == ym)
        cash = sum(m["cashMonthly"] for m in ms)
        equity = sum(m["equity"] for m in ms)
        profit = sum(m["profit"] for m in ms)
        invested = sum(m["invested"] for m in ms)
        self.k_rent.text = gl.money(collected)
        self.dom_nodes["k_rent_sub"].textContent = "of " + gl.money(expected) + " expected"
        self.k_cash.text = gl.signed(cash)
        self.k_cash.role = ["kpi-val", gl.tone(cash)]
        self.k_equity.text = gl.money(equity, short=True)
        self.k_profit.text = gl.signed(profit, short=True)
        self.k_profit.role = ["kpi-val", gl.tone(profit)]
        self.dom_nodes["k_profit_sub"].textContent = "profit on " + gl.money(invested, short=True) + " put in"
        self.props_panel.items = [{"p": p, "m": m} for p, m in zip(props, ms)]
        hidden = len(d["properties"]) - len(props)
        self.archived_note.text = (state.plural(hidden, "archived property", "archived properties") + " not shown.") if hidden else ""
        self.archived_note.visible = hidden > 0
        att = attention(d)
        self.att_panel.items = att[:8]
        self.calm.visible = not att
        b = gl.badges(d.get("stats"))
        self.badges_panel.items = [{"icon": i, "text": t} for i, t in b]
        self.badges_hint.visible = bool(b)
        self.no_badges.visible = not b

    # ---- actions
    def _add_property(self):
        r = alert(PropertyForm(), buttons=[], role="app-dialog", large=True, dismissible=True)
        if r:
            state.toast("Property added", "ok")
            router.go("property", r["property"]["id"])

    @handle("add_prop", "click")
    def add_prop_click(self, **event_args):
        self._add_property()

    @handle("add_prop_empty", "click")
    def add_prop_empty_click(self, **event_args):
        self._add_property()

    def add_house_click(self, event):
        self._add_property()

    @handle("add_entry", "click")
    def add_entry_click(self, **event_args):
        props = gl.active_props()
        r = alert(EntryForm(defaults={"property_id": props[0]["id"] if props else None}), buttons=[], role="app-dialog", large=True, dismissible=True)
        if r:
            state.toast("Saved", "ok")
            self._draw()

    @handle("sample_button", "click")
    def sample_button_click(self, **event_args):
        self.sample_button.enabled = False
        try:
            r = state.call("load_sample")
        finally:
            self.sample_button.enabled = True
        if r:
            state.toast("Sample loaded: have a look around!", "ok")
            self._draw()

    @handle("clear_sample", "click")
    def clear_sample_click(self, **event_args):
        if confirm("The sample properties, tenants, records and ledger entries are removed. Anything you added yourself stays.",
                   title="Clear the sample?", buttons=[("Cancel", False), ("Clear it", True)], role="app-dialog"):
            if state.call("clear_sample"):
                state.toast("Sample cleared", "ok")
                self._draw()
