import anvil.js
from anvil import *
from anvil.js import window

from ._anvil_designer import DealTemplate
from ... import gl, router, state
from ...Dialogs.MortgageForm import MortgageForm

CALC_FIELDS = ("price", "down", "rate", "amort", "rent", "costs")


class Deal(DealTemplate):
    """#deal, #deal/<propertyId>[/mortgage], #deal/calculator: "Am I getting a good deal?" Sell today (price and
    selling-cost sliders, profit, the verdict, where the profit comes from), keep it (appreciation, years, rent and cost
    growth -> value vs debt chart, sensitivity tiles, milestones), the mortgage (payments, interest vs principal by year,
    rate-at-renewal slider), ratios. Plus the free mortgage + cash flow calculator. The maths is gl.js's (GL.dealVM ...)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.args = list(args)
        self.S: dict = {}
        self.pid = None
        self.sens_panel.add_event_handler("x-appr", self._appr)
        for s in (self.s_value, self.s_sell, self.s_appr, self.s_years, self.s_rent, self.s_cost):
            s.add_event_handler("change", self._slid)
        self.s_renew.add_event_handler("change", self._renew_slid)
        for name, value in (("p_fall", -1), ("p_cautious", 2), ("p_typical", 3.5), ("p_hot", 6)):
            b = getattr(self, name)
            b.tag = value
            b.set_event_handler("click", self._preset)
        self.proj_chart.plot(lambda el: gl.draw("drawDealChart", el, self.pid, self.S) if self.pid else None)
        self.amort_chart.plot(lambda el: gl.draw("drawAmort", el, self.pid) if self.pid else None)
        self.calc_chart.plot(lambda el: gl.draw("drawCalc", el, self._calc_values()) if not self.pid else None)
        self._draw(load=True)

    def after_open(self):
        if len(self.args) > 1 and self.args[1] == "mortgage" and self.pid:
            node = self.dom_nodes["mort_card"]
            window.setTimeout(lambda: node.scrollIntoView({"behavior": "smooth"}), 80)

    def _draw(self, load=False):
        if load:
            gl.load()
        d = gl.data()
        props = gl.active_props()
        arg = self.args[0] if self.args else ""
        if arg == "calculator" or not props:
            self.pid = None
        else:
            p = gl.prop(arg)
            self.pid = p["id"] if (p and not p.get("archived")) else props[0]["id"]
        chips = [{"id": p["id"], "name": p["name"], "door": p["door"], "kind": p["kind"], "on": p["id"] == self.pid} for p in props]
        self.chips_panel.items = chips + [{"calc": True, "on": self.pid is None}]
        self.prop_part.visible = self.pid is not None
        self.calc_part.visible = self.pid is None
        if self.pid is None:
            self.lead.text = "Try a deal before you buy it, or test a refinance."
            self._calc_start(d)
            return
        p = gl.prop(self.pid)
        self.lead.text = "Is " + p["name"] + " a good deal? Slide the numbers and see."
        st = gl.vm("dealStartVM", self.pid)
        self.S = {"value": st["value"], "sell": st["sell"], "appr": st["appr"], "years": 10, "rent": 2, "cost": 2.5, "renew": None}
        self.s_value.setup(st["vmin"], st["vmax"], 1000, st["value"], gl.money(st["vmin"], short=True), gl.money(st["vmax"], short=True))
        self.s_sell.setup(0, 10, 0.5, st["sell"], "0%", "10%")
        self.s_appr.setup(-3, 10, 0.25, st["appr"], "−3%", "10%")
        self.s_years.setup(1, 30, 1, 10, "1 year", "30 years")
        self.s_rent.setup(0, 6, 0.5, 2)
        self.s_cost.setup(0, 6, 0.5, 2.5)
        self._mortgage()
        self._update()

    # ---- property: the numbers for the slider values
    def _update(self):
        S, p = self.S, gl.prop(self.pid)
        yrs = state.plural(int(S["years"]), "year")
        self.s_value.shown = gl.money(S["value"])
        self.s_sell.shown = ("%g" % S["sell"]) + "%"
        self.s_appr.shown = ("+" if S["appr"] > 0 else "") + ("%g" % S["appr"]) + "%"
        self.s_years.shown = yrs
        self.s_rent.shown = ("%g" % S["rent"]) + "%"
        self.s_cost.shown = ("%g" % S["cost"]) + "%"
        for name in ("p_fall", "p_cautious", "p_typical", "p_hot"):
            b = getattr(self, name)
            on = float(b.tag) == float(S["appr"])
            b.role = ["dl-preset", "on"] if on else ["dl-preset"]
            state.set_control_attr(b, "aria-pressed", "true" if on else "false")
        v = gl.vm("dealVM", self.pid, S)
        vd = v["verdict"]
        self.dom_nodes["verdict"].className = "dl-verdict " + vd["key"]
        self.verdict_house.show(door=p["door"], kind=p["kind"], glow=vd["glow"], smoke=vd["key"] in ("great", "good"), size=92)
        self.verdict_label.text = vd["label"]
        self.dom_nodes["verdict_text"].textContent = vd["text"]
        t = v["today"]
        d = self.dom_nodes
        d["t_proceeds"].textContent = gl.money(t["proceeds"])
        _signed(d["t_profit"], t["profit"])
        d["t_roi"].textContent = gl.pct(t["roi"] * 100, 0)
        d["t_annual_lbl"].textContent = "Per year (over %.1f yrs)" % t["years"]
        d["t_annual"].textContent = gl.pct(t["annual"] * 100)
        self.why_panel.items = v["why"]
        d["gap"].textContent = ("Cash flow counts what you recorded in the ledger, minus mortgage payments over the same months." if v["hasLedger"]
                                else "No ledger entries yet, so cash flow isn't counted. Record rent and costs on the Money page.")
        f = v["future"]
        d["f_value_lbl"].textContent = "Worth in " + yrs
        d["f_value"].textContent = gl.money(f["value"], short=True)
        d["f_balance"].textContent = gl.money(f["balance"], short=True)
        _signed(d["f_profit"], f["profit"], short=True)
        d["f_annual"].textContent = gl.pct(f["annual"] * 100)
        d["years2"].textContent = yrs
        focus = state.focus_key()
        self.sens_panel.items = [dict(s, on=float(s["a"]) == float(S["appr"])) for s in v["sens"]]
        state.refocus(self.sens_panel, focus)
        self.miles_panel.items = v["miles"]
        r = v["ratios"]
        d["r_cap"].textContent = gl.pct(r["cap"] * 100)
        d["r_coc"].textContent = gl.pct(r["coc"] * 100)
        d["r_rtv"].textContent = gl.pct(r["rtv"] * 100, 2)
        self.proj_chart.redraw()

    def _slid(self, sender, **event_args):
        key = {"s_value": "value", "s_sell": "sell", "s_appr": "appr", "s_years": "years", "s_rent": "rent", "s_cost": "cost"}
        for name, k in key.items():
            if getattr(self, name) is sender:
                self.S[k] = sender.value
        self._update()

    def _preset(self, sender, **event_args):
        self._appr(sender.tag)

    def _appr(self, value, **event_args):
        self.S["appr"] = float(value)
        self.s_appr.value = float(value)
        self._update()

    @handle("keep_button", "click")
    def keep_button_click(self, **event_args):
        S = self.S
        self.keep_button.enabled = False
        try:
            r = state.call("save_estimate", self.pid, S["value"], S["appr"], S["sell"])
        finally:
            self.keep_button.enabled = True
        if r:
            state.toast("Saved as your estimates", "ok")
            gl.load()

    # ---- the mortgage
    def _mortgage(self):
        m = gl.vm("mortgageVM", self.pid)
        self.no_mort.visible = m is None
        self.mort_part.visible = m is not None
        if m is None:
            return
        self._mort_id = m["id"]
        d = self.dom_nodes
        self.mort_title.text = "Mortgage" + (" (first of %d)" % m["count"] if m["count"] > 1 else "")
        state.heading(self.mort_title, 2)
        d["mort_desc"].textContent = ((m["lender"] + " · ") if m["lender"] else "") + gl.money(m["amount"]) + " at %g%% over %g years, " % (m["rate"], m["amort"]) + \
            ("compounded monthly" if m["compounding"] == "monthly" else "compounded twice a year")
        d["m_payment"].textContent = gl.money(m["payment"], cents=True)
        d["m_monthly"].textContent = gl.money(m["monthly"])
        d["m_balance"].textContent = gl.money(m["balance"])
        d["m_interest"].textContent = gl.money(m["interestSoFar"])
        d["m_principal"].textContent = gl.money(m["principalSoFar"])
        upcoming = m["renDays"] >= 0
        d["m_ren_lbl"].textContent = "Renews in" if upcoming else "Renewed"
        d["m_ren"].textContent = state.plural(m["renDays"], "day") if upcoming else gl.fmt_date(m["renews"])
        self.renew_box.visible = upcoming and m["balRen"] > 0
        if self.renew_box.visible:
            if self.S.get("renew") is None:
                self.S["renew"] = m["rate"]
            d["renew_lead"].textContent = "On " + gl.fmt_date(m["renews"]) + " you'll still owe about " + gl.money(m["balRen"]) + ", with %d years left." % m["leftYears"]
            self.s_renew.setup(1, 10, 0.05, self.S["renew"], "1%", "10%")
            self._renew()
        self.amort_chart.redraw()

    def _renew(self):
        r = gl.vm("renewVM", self.pid, self.S["renew"])
        self.s_renew.shown = "%.2f%%" % float(self.S["renew"])
        d = self.dom_nodes
        d["r_monthly"].textContent = gl.money(r["monthly"])
        diff = r["diff"]
        if abs(diff) < 1:
            d["r_diff"].textContent = "No change"
            d["r_diff"].className = ""
        else:
            d["r_diff"].textContent = gl.signed(-diff) + (" more" if diff > 0 else " less")
            d["r_diff"].className = "num gl-" + gl.tone(-diff)

    def _renew_slid(self, **event_args):
        self.S["renew"] = self.s_renew.value
        self._renew()

    @handle("add_mort", "click")
    def add_mort_click(self, **event_args):
        if alert(MortgageForm(property_id=self.pid), buttons=[], role="app-dialog", large=True, dismissible=True):
            self._draw(load=True)

    @handle("edit_mort", "click")
    def edit_mort_click(self, **event_args):
        mo = next((m for m in gl.data()["mortgages"] if m["id"] == self._mort_id), None)
        if mo and alert(MortgageForm(mortgage=mo, property_id=self.pid), buttons=[], role="app-dialog", large=True, dismissible=True):
            self._draw(load=True)

    # ---- the calculator (remembered in this browser, same key as the JavaScript version)
    def _calc_start(self, d):
        c = state.store_get("calc", None) or {}
        dflt = {"price": 500000, "down": 20, "rate": 4.79, "amort": 25, "frequency": "monthly",
                "compounding": (d.get("prefs") or {}).get("compounding") or "semiannual", "rent": 2600, "costs": 650}
        for k, v in dflt.items():
            if c.get(k) in (None, ""):
                c[k] = v
        for k in CALC_FIELDS:
            box = getattr(self, "c_" + k)
            box.text = str(c[k])
            state.set_control_attr(box, "inputmode", "decimal")
            box.set_event_handler("change", self._calc_changed)
        self.c_freq.items = [(label, key) for key, label in gl.FREQ]
        self.c_freq.selected_value = c["frequency"]
        self.c_comp.items = [("Twice a year (Canada)", "semiannual"), ("Monthly (US)", "monthly")]
        self.c_comp.selected_value = c["compounding"]
        self.c_freq.set_event_handler("change", self._calc_changed)
        self.c_comp.set_event_handler("change", self._calc_changed)
        self._calc()

    def _calc_values(self):
        v = {k: gl.num(getattr(self, "c_" + k).text) for k in CALC_FIELDS}
        v["frequency"] = self.c_freq.selected_value or "monthly"
        v["compounding"] = self.c_comp.selected_value or "semiannual"
        return v

    def _calc_changed(self, **event_args):
        self._calc()

    def _calc(self):
        raw = {k: getattr(self, "c_" + k).text for k in CALC_FIELDS}
        raw["frequency"] = self.c_freq.selected_value
        raw["compounding"] = self.c_comp.selected_value
        state.store_set("calc", raw)
        r = gl.vm("calcVM", self._calc_values())
        d = self.dom_nodes
        d["c_payment"].textContent = gl.money(r["payment"], cents=True)
        d["c_monthly"].textContent = gl.money(r["monthly"])
        _signed(d["c_cash"], r["cash"])
        d["c_interest"].textContent = gl.money(r["interest"], short=True)
        d["c_loan"].textContent = gl.money(r["loan"], short=True)
        d["c_coc"].textContent = gl.pct(r["coc"] * 100)
        self.calc_chart.redraw()


def _signed(node, v, short=False):
    node.textContent = gl.signed(v, short=short)
    node.className = "num gl-" + gl.tone(v)
