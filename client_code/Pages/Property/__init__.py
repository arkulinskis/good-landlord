from anvil import *

from ._anvil_designer import PropertyTemplate
from ... import gl, router, state
from ...Dialogs.EntryForm import EntryForm
from ...Dialogs.MortgageForm import MortgageForm
from ...Dialogs.PropertyForm import PropertyForm
from ...Dialogs.TenancyForm import TenancyForm


class Property(PropertyTemplate):
    """#property/<id> (Operate): one rental. Its house, the key numbers, money in and out (chart + recent entries),
    tenants (record + private link), the mortgage(s), notes. Edit, archive, delete."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.pid = args[0] if args else ""
        self.entries_panel.add_event_handler("x-entry", self._entry)
        self.mort_panel.add_event_handler("x-edit-mortgage", self._edit_mortgage)
        self.chart.plot(lambda el: gl.draw("drawPropChart", el, self.pid))
        self._draw(load=True)

    def _draw(self, load=False):
        if load:
            gl.load()
        d = gl.data()
        p = gl.prop(self.pid)
        self.missing.visible = p is None
        self.main_part.visible = p is not None
        if p is None:
            return
        self.p = p
        m = gl.metrics(p["id"])
        kind = gl.KIND_LABEL.get(p["kind"], "")
        self.archived_banner.visible = bool(p.get("archived"))
        self.house.show(door=p["door"], kind=p["kind"], glow=m["glow"], smoke=m["cashMonthly"] > 0, size=110)
        self.title.text = p["name"]
        state.heading(self.title, 1)
        bits = [kind + " · " + state.plural(p["units"], "unit") + (" · sample" if p.get("demo") else "")]
        if p.get("address"):
            bits.append(p["address"])
        if p.get("purchase_date"):
            bits.append("bought " + gl.fmt_date(p["purchase_date"], "my") + " for " + gl.money(p["purchase_price"]))
        self.dom_nodes["sub"].textContent = " · ".join(bits)
        self.dom_nodes["deal_link"].setAttribute("href", router.href("deal", p["id"]))
        self.dom_nodes["ledger_link"].setAttribute("href", router.href("money", "ledger", p["id"]))
        self.k_value.text = gl.money(m["value"])
        self.dom_nodes["k_value_sub"].textContent = ("+" if m["appreciationGain"] >= 0 else "") + gl.money(m["appreciationGain"]) + " since you bought"
        self.k_owed.text = gl.money(m["balance"])
        self.dom_nodes["k_owed_sub"].textContent = (gl.money(m["mortMonthly"]) + " a month") if m["mortgages"] else "no mortgage added"
        self.k_equity.text = gl.money(m["equity"])
        self.dom_nodes["k_equity_sub"].textContent = "%d%% of the value is yours" % (round(m["equity"] / m["value"] * 100) if m["value"] else 0)
        self.k_cash.text = gl.signed(m["cashMonthly"])
        self.k_cash.role = ["kpi-val", gl.tone(m["cashMonthly"])]
        self.dom_nodes["k_cash_sub"].textContent = "a month: " + gl.money(m["rent"]) + " rent − " + gl.money(m["opexMonthly"]) + " costs − mortgage"
        led = [dict(e, compact=True) for e in d["ledger"] if e.get("property_id") == p["id"]]
        self.entries_panel.items = led[:6]
        tens = [t for t in d["tenancies"] if t["property_id"] == p["id"]]
        self.tenants_panel.items = tens
        self.no_tenants.visible = not tens
        morts = [dict(x, property_id=p["id"]) for x in gl.vm("mortgagesVM", p["id"])]
        self.mort_panel.items = morts
        self.add_mort_top.visible = not morts
        self.add_mort_more.visible = bool(morts)
        self.no_mort.visible = not morts
        self.notes_card.visible = bool(p.get("notes"))
        self.notes.text = p.get("notes") or ""
        self.archive_button.visible = not p.get("archived")
        self.unarchive_button.visible = bool(p.get("archived"))
        self.chart.redraw()

    def _dialog(self, form):
        return alert(form, buttons=[], role="app-dialog", large=True, dismissible=True)

    # ---- actions
    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        if self._dialog(PropertyForm(prop=self.p)):
            state.toast("Saved", "ok")
            self._draw(load=True)

    def _add_mortgage(self):
        if self._dialog(MortgageForm(property_id=self.pid)):
            state.toast("Mortgage saved", "ok")
            self._draw(load=True)

    @handle("add_mort_top", "click")
    def add_mort_top_click(self, **event_args):
        self._add_mortgage()

    @handle("add_mort_more", "click")
    def add_mort_more_click(self, **event_args):
        self._add_mortgage()

    def _edit_mortgage(self, mortgage_id, **event_args):
        mo = next((m for m in gl.data()["mortgages"] if m["id"] == mortgage_id), None)
        if mo and self._dialog(MortgageForm(mortgage=mo, property_id=self.pid)):
            self._draw(load=True)

    @handle("add_tenant", "click")
    def add_tenant_click(self, **event_args):
        r = self._dialog(TenancyForm(property_id=self.pid))
        if r:
            state.toast("Record opened", "ok")
            router.go("tenancy", r["tenancy"]["id"], "share")

    def _add_entry(self, kind):
        defaults = {"property_id": self.pid, "kind": kind, "category": "rent" if kind == "income" else "repairs"}
        if self._dialog(EntryForm(defaults=defaults)):
            state.toast("Saved", "ok")
            self._draw(load=True)

    @handle("add_expense", "click")
    def add_expense_click(self, **event_args):
        self._add_entry("expense")

    @handle("add_income", "click")
    def add_income_click(self, **event_args):
        self._add_entry("income")

    def _entry(self, entry, **event_args):
        e = next((x for x in gl.data()["ledger"] if x["id"] == entry["id"]), None)
        if e and self._dialog(EntryForm(entry=e)):
            self._draw(load=True)

    def _archive(self, flag):
        if state.call("archive_property", self.pid, flag):
            state.toast("Archived" if flag else "Back in your totals", "ok")
            self._draw(load=True)

    @handle("archive_button", "click")
    def archive_button_click(self, **event_args):
        self._archive(True)

    @handle("unarchive_button", "click")
    def unarchive_button_click(self, **event_args):
        self._archive(False)

    @handle("unarchive_top", "click")
    def unarchive_top_click(self, **event_args):
        self._archive(False)

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("Its mortgage and ledger entries are deleted too. A property with tenancy records can only be archived.",
                   title="Delete " + self.p["name"] + "?", buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_property", self.pid):
                state.toast("Deleted")
                router.go("home")
