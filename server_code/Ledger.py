"""Money in and out: rent and other income, expenses sorted into tax-claimable categories, the rent roll.

Mortgage payments are NOT ledger entries: the browser works them out from the mortgage (and splits
interest, which is claimable, from principal, which isn't).
"""
import datetime as dt

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Record

# claim: "yes" (deductible this year), "capital" (depreciated over years), "no" (not claimable). income: None.
CATEGORIES = [
    {"id": "rent", "kind": "income", "label": "Rent", "claim": None, "hint": "Monthly rent from your tenants"},
    {"id": "parking", "kind": "income", "label": "Parking & storage", "claim": None, "hint": ""},
    {"id": "laundry", "kind": "income", "label": "Laundry & vending", "claim": None, "hint": ""},
    {"id": "fees", "kind": "income", "label": "Late fees & charges", "claim": None, "hint": ""},
    {"id": "other_income", "kind": "income", "label": "Other income", "claim": None, "hint": ""},
    {"id": "repairs", "kind": "expense", "label": "Repairs & maintenance", "claim": "yes", "hint": "Fixing what's already there: taps, paint, appliance repairs"},
    {"id": "property_tax", "kind": "expense", "label": "Property & school taxes", "claim": "yes", "hint": ""},
    {"id": "insurance", "kind": "expense", "label": "Insurance", "claim": "yes", "hint": "Landlord or building insurance"},
    {"id": "utilities", "kind": "expense", "label": "Utilities", "claim": "yes", "hint": "Heat, power or water you pay for the tenants"},
    {"id": "condo_fees", "kind": "expense", "label": "Condo / HOA fees", "claim": "yes", "hint": ""},
    {"id": "management", "kind": "expense", "label": "Management & admin", "claim": "yes", "hint": "Property manager, rent collection, software"},
    {"id": "professional", "kind": "expense", "label": "Legal & accounting", "claim": "yes", "hint": "Leases, tribunal fees, tax preparation"},
    {"id": "advertising", "kind": "expense", "label": "Advertising", "claim": "yes", "hint": "Listings, signs, photos"},
    {"id": "wages", "kind": "expense", "label": "Wages & services", "claim": "yes", "hint": "Cleaning, snow removal, caretaker"},
    {"id": "interest_other", "kind": "expense", "label": "Bank charges & other interest", "claim": "yes", "hint": "Not your mortgage: that's counted for you"},
    {"id": "travel", "kind": "expense", "label": "Travel to your rentals", "claim": "yes", "hint": "Local trips to collect rent or do repairs"},
    {"id": "office", "kind": "expense", "label": "Office & supplies", "claim": "yes", "hint": ""},
    {"id": "other_expense", "kind": "expense", "label": "Other deductible", "claim": "yes", "hint": ""},
    {"id": "capital", "kind": "expense", "label": "Improvements (capital)", "claim": "capital", "hint": "New roof, new kitchen, additions: depreciated over years, not claimed all at once"},
    {"id": "personal", "kind": "expense", "label": "Not claimable", "claim": "no", "hint": "Fines, your own use, mortgage principal"},
]
BY_ID = {c["id"]: c for c in CATEGORIES}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def month_label(ym):
    y, m = ym.split("-")
    return "%s %s" % (MONTHS[int(m) - 1], y)


def money(amount, currency):
    return "%s %s" % ("{:,.2f}".format(amount), currency)


def valid_month(value):
    s = C.text(value, 7)
    try:
        y, m = s.split("-")
        if len(y) == 4 and 1 <= int(m) <= 12:
            return "%s-%02d" % (y, int(m))
    except ValueError:
        pass
    return None


def entry_dict(r):
    p, t, k = r["property"], r["tenancy"], r["task"]
    return {"id": r.get_id(), "property_id": p.get_id() if p is not None else None,
            "tenancy_id": t.get_id() if t is not None else None, "task_id": k.get_id() if k is not None else None,
            "kind": r["kind"], "category": r["category"], "amount": r["amount"] or 0, "date": C.iso(r["date"]),
            "memo": r["memo"] or "", "rent_month": r["rent_month"]}


def _owned(table, row_id, me):
    r = C.row_by_id(table, row_id)
    return r if (r is not None and r["owner"] == me) else None


def _fields(d, me):
    cat = BY_ID.get(d.get("category"))
    if cat is None:
        return None, "Choose a category."
    amount = C.num(d.get("amount"), 0, 1e9, 0)
    if amount <= 0:
        return None, "Enter an amount above zero."
    prop = _owned(app_tables.properties, d.get("property_id"), me)
    if prop is None:
        return None, "Choose which property this is for."
    tenancy = None
    if d.get("tenancy_id"):
        tenancy = _owned(app_tables.tenancies, d.get("tenancy_id"), me)
        if tenancy is None or tenancy["property"] != prop:
            return None, "That tenant isn't at this property."
    day = C.date(d.get("date"), C.now().date())
    rent_month = None
    if cat["id"] == "rent":
        rent_month = valid_month(d.get("rent_month")) or day.strftime("%Y-%m")
    return {"property": prop, "tenancy": tenancy, "kind": cat["kind"], "category": cat["id"], "amount": round(amount, 2),
            "date": day, "memo": C.text(d.get("memo"), 200), "rent_month": rent_month}, None


@anvil.server.callable(require_user=True)
def add_entry(data):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    fields, err = _fields(data, me)
    if err:
        return C.fail(err)
    if C.rate_limited("add_entry", 300, 3600):
        return C.fail("That's a lot of entries in one hour. Please try again later.")
    r = app_tables.ledger.add_row(owner=me, created=C.now(), is_demo=bool(fields["property"]["is_demo"]), **fields)
    return C.ok(entry=entry_dict(r))


@anvil.server.callable(require_user=True)
def update_entry(entry_id, data):
    me = C.require_user()
    r = _owned(app_tables.ledger, entry_id, me)
    if r is None:
        return C.fail("That entry isn't yours, or it was deleted.")
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    fields, err = _fields(data, me)
    if err:
        return C.fail(err)
    r.update(**fields)
    return C.ok(entry=entry_dict(r))


@anvil.server.callable(require_user=True)
def delete_entry(entry_id):
    me = C.require_user()
    r = _owned(app_tables.ledger, entry_id, me)
    if r is None:
        return C.ok()
    t = r["tenancy"]
    if r["category"] == "rent" and t is not None and r["rent_month"]:
        Record.append(t, "event", "landlord", C.name_of(me),
                      "Removed the rent record for %s." % month_label(r["rent_month"]), event="rent_removed",
                      is_demo=t["is_demo"])
    r.delete()
    return C.ok()


@anvil.server.callable(require_user=True)
def mark_rent_paid(tenancy_id, month, amount=None, paid_on=None):
    """Rent roll: record a month's rent as received. It also goes into the tenancy record as a receipt."""
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    ym = valid_month(month)
    if ym is None:
        return C.fail("Pick a month.")
    if len(app_tables.ledger.search(tenancy=t, category="rent", rent_month=ym)):
        return C.fail("Rent for %s is already recorded." % month_label(ym))
    amount = C.num(amount, 0, 1e8, t["rent"] or 0)
    if amount <= 0:
        return C.fail("Enter the amount received.")
    y, m = [int(x) for x in ym.split("-")]
    default_day = dt.date(y, m, min(int(t["due_day"] or 1), 28))
    day = C.date(paid_on, min(default_day, C.now().date()) if default_day <= C.now().date() else C.now().date())
    r = app_tables.ledger.add_row(owner=me, property=t["property"], tenancy=t, kind="income", category="rent",
                                  amount=round(amount, 2), date=day, memo="Rent %s" % month_label(ym), rent_month=ym,
                                  created=C.now(), is_demo=bool(t["is_demo"]))
    from . import Portfolio
    cur = Portfolio.prefs_of(me)["currency"]
    Record.append(t, "event", "landlord", C.name_of(me),
                  "Rent for %s received: %s (paid %s)." % (month_label(ym), money(amount, cur), day.isoformat()),
                  event="rent_paid", is_demo=t["is_demo"])
    return C.ok(entry=entry_dict(r))
