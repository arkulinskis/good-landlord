from anvil import *
from anvil.js import window

from ._anvil_designer import CalculatorTemplate
from ... import gl, router, state

FIELDS = ("price", "down", "rate", "amort", "rent", "costs")
DEFAULTS = {"price": "500000", "down": "20", "rate": "4.79", "amort": "25", "rent": "2600", "costs": "650",
            "freq": "monthly", "comp": "semiannual", "cur": "CAD"}
CURRENCIES = ["CAD", "USD", "EUR", "GBP", "AUD", "NZD", "CHF"]


def parse_args(arg):
    """'price=500000&down=20&...' (the shareable address) -> dict of the known keys."""
    out = {}
    for part in (arg or "").split("&"):
        k, _, v = part.partition("=")
        if k in DEFAULTS and v:
            out[k] = v[:20]
    return out


class Calculator(CalculatorTemplate):
    """#calculator[/price=..&down=..] (anyone, no sign-in): the free rental property calculator. Payment, cash flow,
    cash-on-cash (gl.js GL.calcVM, the same maths as the Deal check), a plain-words verdict with a glowing house, four
    rules of thumb (cap rate, debt cover, break-even rent, 1% rule), the balance chart, and a share link that carries
    the numbers in the address. No server call. Remembered in this browser (key calc.public)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        state.heading(self.title, 1)
        v = dict(DEFAULTS)
        saved = state.store_get("calc.public", None)
        if saved is not None:
            for k in DEFAULTS:
                x = saved.get(k)  # a JavaScript object from browser storage
                if x not in (None, ""):
                    v[k] = str(x)
        v.update(parse_args(args[0] if args else ""))
        for k in FIELDS:
            box = getattr(self, "c_" + k)
            box.text = v[k]
            state.set_control_attr(box, "inputmode", "decimal")
            box.set_event_handler("change", self._changed)
        self.c_freq.items = [(label, key) for key, label in gl.FREQ]
        self.c_freq.selected_value = v["freq"] if v["freq"] in [k for k, _ in gl.FREQ] else "monthly"
        self.c_comp.items = [("Twice a year (Canada)", "semiannual"), ("Monthly (US)", "monthly")]
        self.c_comp.selected_value = v["comp"] if v["comp"] in ("semiannual", "monthly") else "semiannual"
        self.c_cur.items = CURRENCIES
        self.c_cur.selected_value = v["cur"] if v["cur"] in CURRENCIES else "CAD"
        for dd, label in ((self.c_freq, "Payments"), (self.c_comp, "Compounding"), (self.c_cur, "Currency")):
            dd.set_event_handler("change", self._changed)
            state.set_control_attr(dd, "aria-label", label)
        signed_in = bool(state.me())
        self.guest_cta.visible = not signed_in
        self.member_cta.visible = signed_in
        self.calc_chart.plot(lambda el: gl.draw("drawCalc", el, self._values()))
        self._calc(save_address=False)

    def _raw(self):
        r = {k: (getattr(self, "c_" + k).text or "").strip() for k in FIELDS}
        r.update(freq=self.c_freq.selected_value or "monthly", comp=self.c_comp.selected_value or "semiannual",
                 cur=self.c_cur.selected_value or "CAD")
        return r

    def _values(self):
        v = {k: gl.num(getattr(self, "c_" + k).text) for k in FIELDS}
        v["frequency"] = self.c_freq.selected_value or "monthly"
        v["compounding"] = self.c_comp.selected_value or "semiannual"
        return v

    def _query(self):
        return "&".join("%s=%s" % (k, "".join(ch for ch in str(x) if ch.isalnum() or ch in ".-")) for k, x in self._raw().items())

    def _changed(self, **event_args):
        self._calc()

    def _calc(self, save_address=True):
        raw = self._raw()
        state.store_set("calc.public", raw)
        if save_address:
            router.replace("calculator", self._query())
        gl.set_currency(raw["cur"])
        v = self._values()
        r = gl.vm("calcVM", v)
        d = self.dom_nodes
        d["c_payment"].textContent = gl.money(r["payment"], cents=True)
        d["c_monthly"].textContent = gl.money(r["monthly"])
        d["c_cash"].textContent = gl.signed(r["cash"])
        d["c_cash"].className = "num gl-" + gl.tone(r["cash"])
        d["c_coc"].textContent = gl.pct(r["coc"] * 100)
        d["c_loan"].textContent = gl.money(r["loan"], short=True)
        d["c_interest"].textContent = gl.money(r["interest"], short=True)
        price, rent, costs, mort = v["price"], v["rent"], v["costs"], r["monthly"]
        noi = rent - costs
        cap = (noi * 12 / price * 100) if price > 0 else 0
        dscr = (noi / mort) if mort > 0 else 0
        breakeven = mort + costs
        one = (rent / price * 100) if price > 0 else 0
        self._rule("r1", "%.1f%%" % cap, "good" if cap >= 5 else "warn" if cap >= 3.5 else "bad")
        self._rule("r2", ("%.2f" % dscr) if mort > 0 else "No mortgage", "good" if (dscr >= 1.2 or mort <= 0) else "warn" if dscr >= 1 else "bad")
        self._rule("r3", gl.money(breakeven), "good" if rent >= breakeven * 1.05 else "warn" if rent >= breakeven else "bad")
        self._rule("r4", "%.2f%%" % one, "good" if one >= 0.8 else "warn" if one >= 0.5 else "bad")
        self._verdict(r["cash"], r["coc"] * 100, price)
        self.calc_chart.redraw()

    def _rule(self, key, value, tone):
        d = self.dom_nodes
        d[key + "_v"].textContent = value
        d[key + "_dot"].className = "cx-dot " + tone
        d[key + "_dot"].setAttribute("title", {"good": "Looks healthy", "warn": "Borderline", "bad": "Weak"}[tone])

    def _verdict(self, cash, coc, price):
        d = self.dom_nodes
        if price <= 0:
            head, text, glow = "Type a price to start", "Then the mortgage, the rent and the monthly costs.", 0.2
        elif cash < 0:
            head = "Costs you %s a month" % gl.money(-cash)
            text = "The rent doesn't cover the mortgage and costs. It can still pay off through price growth and the mortgage paid down, but you top it up every month."
            glow = 0.15
        elif coc < 4:
            head, text, glow = "Thin: %s a month" % gl.signed(cash), "It pays for itself with a little left over. One repair or an empty month wipes out a year.", 0.45
        elif coc < 8:
            head, text, glow = "Solid: %s a month" % gl.signed(cash), "A healthy cash flow for the money you put in, before price growth.", 0.75
        else:
            head, text, glow = "Strong: %s a month" % gl.signed(cash), "Great cash flow for the money you put in. Double-check the rent and the costs are realistic.", 1.0
        d["v_head"].textContent = head
        d["v_text"].textContent = text
        self.house.show(door="honey", glow=glow, smoke=cash > 0, size=84)

    @handle("share_button", "click")
    def share_button_click(self, **event_args):
        router.replace("calculator", self._query())
        gl.copy(str(window.location.href))

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        state.store_set("calc.public", None)
        for k in FIELDS:
            getattr(self, "c_" + k).text = DEFAULTS[k]
        self.c_freq.selected_value = DEFAULTS["freq"]
        self.c_comp.selected_value = DEFAULTS["comp"]
        self._calc()
