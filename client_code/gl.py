"""Good Landlord's bridge to its engine (theme/assets/gl.js) and the landlord's portfolio cache.

    gl.load()                  get_portfolio (ONE call: properties, mortgages, tenancies, ledger, tasks, prefs, stats)
                               -> kept here (gl.data()) and handed to the engine (GL.setData) for the maths
    gl.metrics(pid, ...)       a property's numbers (cash flow, equity, profit if sold, verdict ...) as a dict
    gl.money(v, ...)           the landlord's currency, the browser's number format ("−$1,234", "+$612", "$1.2M")
    gl.fmt_date / ago / ...    dates in the browser's own format
    gl.house_svg(...)          the SVG house (Components/House uses it)
The maths and drawing stay JavaScript (moved unchanged from the JavaScript version); everything the Forms show is
built in Python from these plain values.
"""
import json

import anvil.js
import anvil.server
from anvil.js import window

from . import state

_d: dict = {"data": None}

DOORS = [("red", "#b4502a"), ("honey", "#e19a35"), ("sage", "#6f8f58"), ("blue", "#3f6f98"), ("plum", "#7d4a6a"),
         ("walnut", "#6b4a33")]
KINDS = [("house", "House"), ("duplex", "Duplex"), ("triplex", "Triplex"), ("condo", "Condo"),
         ("apartment", "Apartment building"), ("townhouse", "Townhouse"), ("cottage", "Cottage"), ("other", "Other")]
KIND_LABEL = dict(KINDS)
FREQ = [("monthly", "Monthly"), ("semi_monthly", "Twice a month"), ("biweekly", "Every 2 weeks"),
        ("accelerated_biweekly", "Every 2 weeks (accelerated)"), ("weekly", "Weekly")]
COMPOUNDING = [("semiannual", "Twice a year (Canadian fixed rate)"), ("monthly", "Monthly (US, variable rates)")]
STATUS = [("requested", "Requested"), ("acknowledged", "Seen"), ("scheduled", "Scheduled"), ("in_progress", "In progress"),
          ("done", "Done"), ("declined", "Declined")]
STATUS_LABEL = dict(STATUS)
TASK_CATS = [("plumbing", "Plumbing"), ("heating", "Heating & cooling"), ("electrical", "Electrical"),
             ("appliance", "Appliance"), ("doors_windows", "Doors & windows"), ("pests", "Pests"),
             ("outdoor", "Outdoor & yard"), ("safety", "Safety (alarms, locks)"), ("cleaning", "Cleaning"),
             ("other", "Something else")]
TASK_CAT_LABEL = dict(TASK_CATS)
PRIORITIES = [("low", "Whenever is convenient"), ("normal", "Soon"), ("urgent", "Urgent (safety, no heat, water leak)")]
REGIONS = [("ca", "Canada"), ("qc", "Québec"), ("us", "United States"), ("uk", "United Kingdom"), ("other", "Elsewhere")]
CURRENCIES = [("CAD", "Canadian dollar (CAD)"), ("USD", "US dollar (USD)"), ("EUR", "Euro (EUR)"),
              ("GBP", "Pound sterling (GBP)"), ("AUD", "Australian dollar (AUD)"), ("NZD", "New Zealand dollar (NZD)"),
              ("CHF", "Swiss franc (CHF)")]
TAX_FORM = {
    "ca": "These lines follow the CRA's Form T776 (Statement of Real Estate Rentals).",
    "qc": "These lines follow the CRA's Form T776; in Québec you also report rental income on form TP-128.",
    "us": "These lines follow the IRS Schedule E (Supplemental Income and Loss).",
    "uk": "These lines follow the SA105 UK property pages. Note: in the UK, mortgage interest gets a 20% tax credit "
          "instead of being deducted.",
    "other": "Most countries ask for the same lines: rents, then expenses by type.",
}
EV_ICON = {"opened": "seal", "requested": "wrench", "acknowledged": "check", "scheduled": "calendar",
           "in_progress": "wrench", "done": "check", "declined": "x", "confirmed": "heart", "reopened": "refresh",
           "rent_paid": "receipt", "rent_removed": "receipt", "rent_changed": "coins", "ended": "key",
           "reopened_tenancy": "key", "link_reset": "link"}


def _js(value):
    """A Python value (dict/list) as a real JavaScript object for the engine."""
    return window.JSON.parse(json.dumps(value))


def plain(value):
    """An engine reply (a JavaScript object) as Python dicts and lists."""
    if value is None:
        return None
    return json.loads(window.JSON.stringify(value))


# ---------------------------------------------------------------- the portfolio
def load(quiet=False):
    """get_portfolio -> cache + engine. Returns the dict."""
    d = anvil.server.call_s("get_portfolio") if quiet else anvil.server.call("get_portfolio")
    _d["data"] = d
    window.GL.setData(_js(d))
    return d


def data():
    return _d["data"]


def set_currency(code):
    """Pages that don't load the portfolio (the tenant page, a tenancy record) still format money right."""
    window.GL.setCurrency(code or "CAD")


def prop(pid):
    d = _d["data"]
    if not d:
        return None
    for p in d["properties"]:
        if p["id"] == pid:
            return p
    return None


def active_props():
    d = _d["data"]
    return [p for p in d["properties"] if not p.get("archived")] if d else []


def category(cid):
    d = _d["data"]
    for c in (d["categories"] if d else []):
        if c["id"] == cid:
            return c
    return {"id": cid, "label": cid or "", "kind": "expense", "claim": ""}


def tenancy(tid):
    for t in (_d["data"] or {}).get("tenancies", []):
        if t["id"] == tid:
            return t
    return None


def today():
    """'YYYY-MM-DD' (the server's today from the portfolio, else the browser's)."""
    d = _d["data"]
    if d and d.get("today"):
        return d["today"][:10]
    return str(window.GL.todayIso())


def ym(iso):
    return iso[:7]


# ---------------------------------------------------------------- the engine's numbers
def metrics(pid, value=None, sell_pct=None):
    opts = {}
    if value is not None:
        opts["value"] = value
    if sell_pct is not None:
        opts["sellPct"] = sell_pct
    return plain(window.GL.metricsVM(pid, _js(opts)))


def vm(name, *args):
    """Call one of gl.js's *VM functions with plain arguments and get a dict back."""
    js_args = [_js(a) if isinstance(a, (dict, list)) else a for a in args]
    return plain(getattr(window.GL, name)(*js_args))


def draw(name, element, *args):
    """Call one of gl.js's draw* functions into a DOM element (a Chart component's box)."""
    js_args = [_js(a) if isinstance(a, (dict, list)) else a for a in args]
    getattr(window.GL, name)(element, *js_args)


def house_svg(door="red", kind="house", glow=0.8, smoke=False, size=120):
    return str(window.GL.houseFor(_js({"door": door or "red", "kind": kind or "house", "glow": glow,
                                       "smoke": bool(smoke), "size": size})))


# ---------------------------------------------------------------- formatting
def money(v, cents=False, short=False, sign=False):
    return str(window.GL.fmt(v or 0, cents, short, sign))


def signed(v, cents=False, short=False):
    """'+$612' / '−$40' (the sign is always shown)."""
    return money(v, cents=cents, short=short, sign=True)


def tone(v):
    """The role that colours a signed amount: pos (green) or neg (red)."""
    return "pos" if (v or 0) >= 0 else "neg"


def pct(v, digits=1):
    v = v or 0
    return ("" if v >= 0 else "−") + ("%." + str(digits) + "f") % abs(v) + "%"


def fmt_date(iso, style=None):
    """Browser-formatted date. style: None ('3 Nov 2026'), dm, my, mys, wdm, wdmy, full."""
    if not iso:
        return ""
    if style:
        return str(window.GL.dateStyle(iso, style))
    return str(window.GL.fmtDate(iso))


def fmt_datetime(iso):
    return str(window.GL.fmtDateTime(iso)) if iso else ""


def fmt_time(iso):
    return str(window.GL.fmtTime(iso)) if iso else ""


def day_key(iso):
    return str(window.GL.dayKey(iso))


def ago(iso):
    return str(window.GL.ago(iso)) if iso else ""


def month_name(ym_text, short=False):
    return str(window.GL.monthName(ym_text, short))


def days(d):
    if d < 1:
        return "%d h" % max(1, round(d * 24))
    n = round(d * 10) / 10
    text = ("%d" % n) if n == int(n) else str(n)
    return text + (" day" if d < 1.5 else " days")


def hours(h):
    if h < 1:
        return "%d minutes" % max(1, round(h * 60))
    if h < 48:
        n = int(round(h))
        return "%d %s" % (n, "hour" if n == 1 else "hours")
    return "%d days" % int(round(h / 24))


def badges(stats):
    """The landlord's response badges: [(icon, text)]."""
    out = []
    stats = stats or {}
    if stats.get("reply_hours") is not None:
        out.append(("clock", "Usually replies in " + hours(stats["reply_hours"])))
    if stats.get("fix_days") is not None:
        out.append(("wrench", "Fixes things in " + days(stats["fix_days"])))
    if stats.get("requests") and stats.get("answered") == stats.get("requests"):
        out.append(("heart", "Answered every request"))
    return out


def task_when(k):
    if k["status"] == "done":
        return "Done " + ago(k.get("done_at")) + (" · took " + days(k["days_open"]) if k.get("days_open") is not None else "")
    if k["status"] == "scheduled" and k.get("scheduled_for"):
        return "Scheduled for " + fmt_date(k["scheduled_for"], "wdm")
    return "Asked " + ago(k.get("requested_at"))


def first_name(name):
    parts = (name or "").split()
    return parts[0] if parts else ""


def num(text):
    """A typed amount ('$1,200.50') as a float (0 when empty)."""
    s = "".join(ch for ch in str(text or "") if ch.isdigit() or ch in ".-")
    try:
        return float(s) if s not in ("", "-", ".") else 0.0
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- browser things
def copy(text):
    ok = False
    try:
        ok = bool(anvil.js.await_promise(window.GL.copy(text)))
    except Exception:
        ok = False
    state.toast("Link copied" if ok else "Select the link and copy it.", "ok" if ok else None)


def tenant_link(token):
    return str(window.GL.tenantLink(token))


def download_record(filename, record):
    """record = {property, unit, tenant, landlord, seal, entries, tasks}: the whole sealed record as a text file."""
    window.GL.recordFile(filename, json.dumps(record))


def download(filename, text, mime="text/plain;charset=utf-8"):
    window.GL.download(filename, text, mime)


def today_iso_js():
    return str(window.GL.todayIso())


def hour_now():
    return int(window.GL.hourNow())


def window_today_long():
    """'Saturday 7 November' (the portfolio's today, in the browser's language)."""
    return str(window.GL.todayLong())


def days_between(a_iso, b_iso):
    return int(window.GL.daysBetween(a_iso, b_iso))


def iso_days_ago(n):
    return str(window.GL.isoDaysAgo(n))
