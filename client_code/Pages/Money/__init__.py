from anvil import *

from ._anvil_designer import MoneyTemplate
from ... import gl, router, state
from ...Dialogs.EntryForm import EntryForm

TABS = ["ledger", "rent", "tax"]


class Money(MoneyTemplate):
    """#money/ledger[/<propertyId>] (filter, add, edit, CSV), #money/rent (who paid this month, mark paid: the ledger
    row + a receipt in the tenant's record), #money/tax (claimable expenses by category + mortgage interest worked out
    from the loan, printable)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = args[0] if args and args[0] in TABS else "ledger"
        self.f = {"prop": (args[1] if len(args) > 1 else None) or state.store_get("money.prop", "") or "", "year": "", "kind": "all", "cat": ""}
        self.rent_month: str = ""
        self.tax_year: str = ""
        for name in TABS:
            getattr(self, "tab_" + name).classes["on"] = name == self.tab
        self.months_panel.add_event_handler("x-entry", self._entry)
        self.rent_panel.add_event_handler("x-entry", self._entry)
        self.rent_panel.add_event_handler("x-paid", self._paid)
        gl.load()
        self._redraw()

    # ---- helpers
    def _years(self):
        ys = {gl.today()[:4]}
        for e in gl.data()["ledger"]:
            ys.add(e["date"][:4])
        return sorted(ys, reverse=True)

    def _prop_items(self):
        return [("All properties", "")] + [(p["name"] + (" (archived)" if p.get("archived") else ""), p["id"]) for p in gl.data()["properties"]]

    def _redraw(self):
        d = gl.data()
        none = not d["properties"]
        self.no_props.visible = none and self.tab == "ledger"
        self.ledger_part.visible = self.tab == "ledger" and not none
        self.rent_part.visible = self.tab == "rent"
        self.tax_part.visible = self.tab == "tax"
        if self.tab == "ledger" and not none:
            self._ledger()
        elif self.tab == "rent":
            self._rent()
        elif self.tab == "tax":
            self._tax()

    def _rows(self, with_kind=True):
        f = self.f
        return [e for e in gl.data()["ledger"] if (not f["prop"] or e.get("property_id") == f["prop"]) and (not f["year"] or e["date"][:4] == f["year"])
                and (not with_kind or f["kind"] == "all" or e["kind"] == f["kind"]) and (not with_kind or not f["cat"] or e["category"] == f["cat"])]

    # ---- ledger
    def _ledger(self):
        d, f = gl.data(), self.f
        ids = [p["id"] for p in d["properties"]]
        if f["prop"] not in ids:
            f["prop"] = ""
        self.f_prop.items = self._prop_items()
        self.f_prop.selected_value = f["prop"]
        self.f_year.items = [("All years", "")] + [(y, y) for y in self._years()]
        self.f_year.selected_value = f["year"]
        self.f_cat.items = [("All categories", "")] + [(c["label"], c["id"]) for c in d["categories"]]
        self.f_cat.selected_value = f["cat"]
        for box, name in ((self.f_prop, "Property"), (self.f_year, "Year"), (self.f_cat, "Category")):
            state.set_control_attr(box, "aria-label", name)
        for el, key in ((self.k_all, "all"), (self.k_in, "income"), (self.k_out, "expense")):
            el.classes["on"] = f["kind"] == key
        rows = self._rows()
        inc = sum(e["amount"] for e in rows if e["kind"] == "income")
        out = sum(e["amount"] for e in rows if e["kind"] != "income")
        self.s_in.text = gl.money(inc)
        self.s_out.text = gl.money(out)
        self.s_diff.text = gl.signed(inc - out)
        self.s_diff.role = ["kpi-val", gl.tone(inc - out)]
        groups, order = {}, []
        for e in rows:
            k = e["date"][:7]
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(e)
        self.months_panel.items = [{"ym": k, "entries": groups[k]} for k in order]
        self.no_rows.visible = not order

    @handle("f_prop", "change")
    def f_prop_change(self, **event_args):
        self.f["prop"] = self.f_prop.selected_value or ""
        state.store_set("money.prop", self.f["prop"])
        self._ledger()

    @handle("f_year", "change")
    def f_year_change(self, **event_args):
        self.f["year"] = self.f_year.selected_value or ""
        self._ledger()

    @handle("f_cat", "change")
    def f_cat_change(self, **event_args):
        self.f["cat"] = self.f_cat.selected_value or ""
        self._ledger()

    def kind_click(self, event):
        self.f["kind"] = event.currentTarget.getAttribute("data-kind")
        self._ledger()

    @handle("csv_button", "click")
    def csv_button_click(self, **event_args):
        def q(s):
            s = "" if s is None else str(s)
            return '"' + s.replace('"', '""') + '"' if ('"' in s or "," in s or "\n" in s) else s
        lines = [",".join(["date", "property", "kind", "category", "claimable", "amount", "memo"])]
        for e in self._rows(with_kind=False):
            c = gl.category(e["category"])
            p = gl.prop(e.get("property_id")) or {}
            lines.append(",".join([e["date"], q(p.get("name")), e["kind"], q(c.get("label")), c.get("claim") or "",
                                   ("" if e["kind"] == "income" else "-") + "%.2f" % e["amount"], q(e.get("memo"))]))
        gl.download("good-landlord-ledger" + ("-" + self.f["year"] if self.f["year"] else "") + ".csv", "\n".join(lines), "text/csv;charset=utf-8")

    # ---- rent roll
    def _rent(self):
        d = gl.data()
        self.rent_month = self.rent_month or gl.today()[:7]
        rm = self.rent_month
        tens = [t for t in d["tenancies"] if t["status"] == "active" or any(e.get("tenancy_id") == t["id"] and e.get("rent_month") == rm for e in d["ledger"])]
        expected, got, rows = 0, 0, []
        for t in tens:
            paid = next((e for e in d["ledger"] if e.get("tenancy_id") == t["id"] and e["category"] == "rent" and e.get("rent_month") == rm), None)
            expected += t["rent"]
            if paid:
                got += paid["amount"]
            due = "%s-%02d" % (rm, t["due_day"])
            rows.append({"t": t, "paid": paid, "days": gl.days_between(due, gl.today())})
        self.month_label.text = gl.month_name(rm)
        state.heading(self.month_label, 2)
        self.this_month.visible = rm != gl.today()[:7]
        self.dom_nodes["collected"].textContent = gl.money(got) + " of " + gl.money(expected) + " collected"
        self.dom_nodes["collected_pct"].textContent = "%d%%" % (round(got / expected * 100) if expected else 0)
        bar = self.dom_nodes["bar"]
        bar.setAttribute("aria-valuenow", str(int(round(got))))
        bar.setAttribute("aria-valuemin", "0")
        bar.setAttribute("aria-valuemax", str(int(round(expected))))
        self.dom_nodes["bar_fill"].style.transform = "scaleX(%.4f)" % (min(1, got / expected) if expected else 0)
        self.rent_panel.items = rows
        self.no_rent.visible = not rows

    def _step_month(self, step):
        if step == 0:
            self.rent_month = gl.today()[:7]
        else:
            y, m = int(self.rent_month[:4]), int(self.rent_month[5:7]) + step
            while m < 1:
                y, m = y - 1, m + 12
            while m > 12:
                y, m = y + 1, m - 12
            self.rent_month = "%04d-%02d" % (y, m)
        self._rent()

    @handle("prev_month", "click")
    def prev_month_click(self, **event_args):
        self._step_month(-1)

    @handle("next_month", "click")
    def next_month_click(self, **event_args):
        self._step_month(1)

    @handle("this_month", "click")
    def this_month_click(self, **event_args):
        self._step_month(0)

    def _paid(self, tenancy, button=None, **event_args):
        if button is not None:
            button.enabled = False
        r = state.call("mark_rent_paid", tenancy["id"], self.rent_month, tenancy["rent"], None)
        if r:
            state.toast("Rent recorded for " + tenancy["tenant_name"], "ok")
            gl.load()
            self._rent()
        elif button is not None:
            button.enabled = True

    # ---- tax summary
    def _tax(self):
        d, f = gl.data(), self.f
        self.tax_year = self.tax_year or gl.today()[:4]
        ty = self.tax_year
        self.t_prop.items = self._prop_items()
        ids = [p["id"] for p in d["properties"]]
        if f["prop"] not in ids:
            f["prop"] = ""
        self.t_prop.selected_value = f["prop"]
        self.t_year.items = [(y, y) for y in self._years()]
        self.t_year.selected_value = ty
        state.set_control_attr(self.t_prop, "aria-label", "Property")
        state.set_control_attr(self.t_year, "aria-label", "Tax year")
        rows = [e for e in d["ledger"] if e["date"][:4] == ty and (not f["prop"] or e.get("property_id") == f["prop"])]
        by = {}
        for e in rows:
            by[e["category"]] = by.get(e["category"], 0) + e["amount"]
        ti = gl.vm("taxInterestVM", ty, f["prop"] or None)
        interest = ti["rows"]
        income_rows = [c for c in d["categories"] if c["kind"] == "income" and by.get(c["id"])]
        exp_rows = [c for c in d["categories"] if c.get("claim") == "yes" and by.get(c["id"])]
        total_inc = sum(by[c["id"]] for c in income_rows)
        total_int = sum(x["v"] for x in interest)
        total_exp = sum(by[c["id"]] for c in exp_rows) + total_int
        cap = [e for e in rows if e["category"] == "capital"]
        nc = [e for e in rows if e["category"] == "personal"]
        principal = sum(x["principal"] for x in interest)
        region = (d.get("prefs") or {}).get("region") or "ca"
        self.tax_title.text = "Rental income " + ty
        state.heading(self.tax_title, 2)
        self.partial.visible = bool(ti["partial"])
        self.dom_nodes["region"].textContent = gl.TAX_FORM.get(region, gl.TAX_FORM["other"])
        self.income_panel.items = [{"label": c["label"], "amount": by[c["id"]]} for c in income_rows] + [{"label": "Gross rental income", "amount": total_inc, "total": True}]
        self.exp_panel.items = ([{"label": c["label"], "amount": by[c["id"]]} for c in exp_rows] +
                                [{"label": "Mortgage interest · " + x["name"], "amount": x["v"], "auto": True} for x in interest] +
                                [{"label": "Total claimable", "amount": total_exp, "total": True}])
        net = total_inc - total_exp
        self.net_label.text = gl.signed(net, cents=True)
        self.net_label.role = ["mn-net", gl.tone(net)]
        self.dom_nodes["net_note"].textContent = ("Gross income minus claimable expenses, before depreciation (capital cost allowance). " +
                                                  ("A rental loss can often reduce your other income's tax; ask your accountant." if net < 0 else ""))
        self.cap_part.visible = bool(cap)
        self.cap_panel.items = [{"label": e.get("memo") or "Improvement", "note": gl.fmt_date(e["date"]) + " · " + ((gl.prop(e.get("property_id")) or {}).get("name") or ""),
                                 "amount": e["amount"]} for e in cap]
        self.nc_part.visible = bool(nc) or principal > 1
        self.nc_panel.items = (([{"label": "Mortgage principal repaid", "note": "(it builds your equity instead)", "amount": principal}] if principal > 1 else []) +
                               [{"label": e.get("memo") or "Not claimable", "amount": e["amount"]} for e in nc])

    @handle("t_prop", "change")
    def t_prop_change(self, **event_args):
        self.f["prop"] = self.t_prop.selected_value or ""
        state.store_set("money.prop", self.f["prop"])
        self._tax()

    @handle("t_year", "change")
    def t_year_change(self, **event_args):
        self.tax_year = self.t_year.selected_value
        self._tax()

    def print_click(self, event):
        from anvil.js import window
        window.print()

    # ---- entries
    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        d = gl.data()
        if not d["properties"]:
            state.toast("Add a property first.")
            return
        first = (gl.active_props() or d["properties"])[0]["id"]
        if alert(EntryForm(defaults={"property_id": self.f["prop"] or first}), buttons=[], role="app-dialog", large=True, dismissible=True):
            state.toast("Saved", "ok")
            gl.load()
            self._redraw()

    def _entry(self, entry, **event_args):
        e = next((x for x in gl.data()["ledger"] if x["id"] == entry["id"]), None)
        if e and alert(EntryForm(entry=e), buttons=[], role="app-dialog", large=True, dismissible=True):
            gl.load()
            self._redraw()
