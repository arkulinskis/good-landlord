"""The landlord's own numbers: properties, mortgages, preferences, and the one call that loads them all.

All money maths (mortgage schedules, cash flow, deal check) runs in the browser (web/pages/_gl.html);
the server stores and checks. Every row belongs to one landlord (owner) and only they can read or change it.
"""
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import common as C
from . import DemoData, Ledger

KINDS = ["house", "duplex", "triplex", "condo", "apartment", "townhouse", "cottage", "other"]
DOORS = ["red", "honey", "sage", "blue", "plum", "walnut"]
FREQUENCIES = ["monthly", "semi_monthly", "biweekly", "accelerated_biweekly", "weekly"]
COMPOUNDING = ["semiannual", "monthly"]
CURRENCIES = ["CAD", "USD", "EUR", "GBP", "AUD", "NZD", "CHF"]
REGIONS = ["ca", "qc", "us", "uk", "other"]
DEFAULT_PREFS = {"currency": "CAD", "region": "ca", "compounding": "semiannual"}


def prefs_of(user):
    p = dict(DEFAULT_PREFS)
    p.update(user["prefs"] or {})
    return p


def owned(table, row_id, me):
    r = C.row_by_id(table, row_id)
    return r if (r is not None and r["owner"] == me) else None


def property_dict(r):
    return {"id": r.get_id(), "name": r["name"], "address": r["address"] or "", "kind": r["kind"] or "house",
            "units": int(r["units"] or 1), "purchase_price": r["purchase_price"] or 0,
            "purchase_date": C.iso(r["purchase_date"]), "down_payment": r["down_payment"] or 0,
            "closing_costs": r["closing_costs"] or 0, "improvements": r["improvements"] or 0,
            "current_value": r["current_value"] or r["purchase_price"] or 0, "value_date": C.iso(r["value_date"]),
            "appreciation": r["appreciation"] if r["appreciation"] is not None else 3.0,
            "selling_pct": r["selling_pct"] if r["selling_pct"] is not None else 5.0,
            "door": r["door"] or "red", "notes": r["notes"] or "", "archived": bool(r["archived"]),
            "demo": bool(r["is_demo"])}


def mortgage_dict(r):
    return {"id": r.get_id(), "property_id": r["property"].get_id(), "lender": r["lender"] or "",
            "amount": r["amount"] or 0, "rate": r["rate"] or 0, "amort_years": r["amort_years"] or 25,
            "term_years": r["term_years"] or 5, "start_date": C.iso(r["start_date"]),
            "frequency": r["frequency"] or "monthly", "compounding": r["compounding"] or "semiannual"}


def tenancy_dict(r, with_counts=True):
    d = {"id": r.get_id(), "property_id": r["property"].get_id(), "property_name": r["property"]["name"],
         "unit": r["unit"] or "", "tenant_name": r["tenant_name"], "tenant_email": r["tenant_email"] or "",
         "rent": r["rent"] or 0, "due_day": int(r["due_day"] or 1), "deposit": r["deposit"] or 0,
         "start_date": C.iso(r["start_date"]), "end_date": C.iso(r["end_date"]), "status": r["status"] or "active",
         "token": r["token"], "tenant_last_visit": C.iso(r["tenant_last_visit"]), "demo": bool(r["is_demo"])}
    if with_counts:
        msgs = list(app_tables.messages.search(tables.order_by("seq", ascending=False), tenancy=r))
        seen = r["landlord_seen"] or 0
        d["entries"] = len(msgs)
        d["unread"] = len([m for m in msgs if m["author_kind"] == "tenant" and m["seq"] > seen])
        last = next((m for m in msgs if m["kind"] == "message"), None)
        d["last_message"] = ({"author_kind": last["author_kind"], "author_name": last["author_name"],
                              "body": (last["body"] or "")[:140], "created": C.iso(last["created"])} if last else None)
        d["open_tasks"] = len([t for t in app_tables.tasks.search(tenancy=r) if t["status"] not in ("done", "declined")])
    return d


@anvil.server.callable(require_user=True)
def get_portfolio():
    """Everything the landlord pages need, in one call."""
    me = C.require_user()
    DemoData.ensure_loaded()
    props = list(app_tables.properties.search(tables.order_by("created"), owner=me))
    from . import Tenancy
    tasks = [Tenancy.task_dict(t) for t in app_tables.tasks.search(tables.order_by("requested_at", ascending=False), owner=me)]
    return {"prefs": prefs_of(me), "categories": Ledger.CATEGORIES,
            "properties": [property_dict(p) for p in props],
            "mortgages": [mortgage_dict(m) for m in app_tables.mortgages.search(tables.order_by("start_date"), owner=me)],
            "tenancies": [tenancy_dict(t) for t in app_tables.tenancies.search(tables.order_by("created"), owner=me)],
            "ledger": [Ledger.entry_dict(e) for e in app_tables.ledger.search(tables.order_by("date", ascending=False), owner=me)],
            "tasks": tasks, "stats": Tenancy.response_stats(me), "has_sample": any(p["is_demo"] for p in props),
            "today": C.iso(C.now().date())}


def _property_fields(d):
    name = C.text(d.get("name"), 80)
    if len(name) < 2:
        return None, "Give the property a name (at least 2 characters)."
    price = C.num(d.get("purchase_price"), 0, 1e10, 0)
    pdate = C.date(d.get("purchase_date"))
    if pdate is not None and pdate > C.now().date():
        return None, "The purchase date can't be in the future."
    return {"name": name, "address": C.text(d.get("address"), 160), "kind": C.choice(d.get("kind"), KINDS, "house"),
            "units": int(C.num(d.get("units"), 1, 200, 1)), "purchase_price": price, "purchase_date": pdate,
            "down_payment": C.num(d.get("down_payment"), 0, 1e10, 0), "closing_costs": C.num(d.get("closing_costs"), 0, 1e9, 0),
            "improvements": C.num(d.get("improvements"), 0, 1e9, 0),
            "current_value": C.num(d.get("current_value"), 0, 1e10, price),
            "value_date": C.date(d.get("value_date"), C.now().date()),
            "appreciation": C.num(d.get("appreciation"), -20, 30, 3.0), "selling_pct": C.num(d.get("selling_pct"), 0, 20, 5.0),
            "door": C.choice(d.get("door"), DOORS, "red"), "notes": C.text(d.get("notes"), 2000, multiline=True)}, None


@anvil.server.callable(require_user=True)
def save_property(data):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    fields, err = _property_fields(data)
    if err:
        return C.fail(err)
    if data.get("id"):
        r = owned(app_tables.properties, data["id"], me)
        if r is None:
            return C.fail("That property isn't yours, or it was deleted.")
        r.update(**fields)
    else:
        if C.rate_limited("add_property", 40, 3600):
            return C.fail("That's a lot of properties in one hour. Please try again later.")
        r = app_tables.properties.add_row(owner=me, archived=False, created=C.now(), is_demo=False, **fields)
    return C.ok(property=property_dict(r))


@anvil.server.callable(require_user=True)
def save_estimate(property_id, current_value=None, appreciation=None, selling_pct=None):
    """The Deal check sliders' "Keep these numbers" button."""
    me = C.require_user()
    r = owned(app_tables.properties, property_id, me)
    if r is None:
        return C.fail("That property isn't yours, or it was deleted.")
    if current_value is not None:
        r["current_value"] = C.num(current_value, 0, 1e10, r["current_value"])
        r["value_date"] = C.now().date()
    if appreciation is not None:
        r["appreciation"] = C.num(appreciation, -20, 30, r["appreciation"])
    if selling_pct is not None:
        r["selling_pct"] = C.num(selling_pct, 0, 20, r["selling_pct"])
    return C.ok(property=property_dict(r))


@anvil.server.callable(require_user=True)
def archive_property(property_id, flag=True):
    me = C.require_user()
    r = owned(app_tables.properties, property_id, me)
    if r is None:
        return C.fail("That property isn't yours, or it was deleted.")
    r["archived"] = bool(flag)
    return C.ok(property=property_dict(r))


@anvil.server.callable(require_user=True)
def delete_property(property_id):
    me = C.require_user()
    r = owned(app_tables.properties, property_id, me)
    if r is None:
        return C.ok()
    if len(app_tables.tenancies.search(property=r)):
        return C.fail("This property has tenancy records, and those are kept for good. Archive the property instead.")
    for e in app_tables.ledger.search(property=r):
        e.delete()
    for m in app_tables.mortgages.search(property=r):
        m.delete()
    r.delete()
    return C.ok()


def _mortgage_fields(d):
    amount = C.num(d.get("amount"), 0, 1e10, 0)
    if amount <= 0:
        return None, "Enter the amount you borrowed."
    rate = C.num(d.get("rate"), 0, 30, None)
    if rate is None:
        return None, "Enter the interest rate, for example 4.79."
    start = C.date(d.get("start_date"))
    if start is None:
        return None, "Enter the date the mortgage started."
    return {"lender": C.text(d.get("lender"), 80), "amount": amount, "rate": rate,
            "amort_years": C.num(d.get("amort_years"), 1, 40, 25), "term_years": C.num(d.get("term_years"), 0.5, 40, 5),
            "start_date": start, "frequency": C.choice(d.get("frequency"), FREQUENCIES, "monthly"),
            "compounding": C.choice(d.get("compounding"), COMPOUNDING, "semiannual")}, None


@anvil.server.callable(require_user=True)
def save_mortgage(data):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    fields, err = _mortgage_fields(data)
    if err:
        return C.fail(err)
    if data.get("id"):
        r = owned(app_tables.mortgages, data["id"], me)
        if r is None:
            return C.fail("That mortgage isn't yours, or it was deleted.")
        r.update(**fields)
    else:
        prop = owned(app_tables.properties, data.get("property_id"), me)
        if prop is None:
            return C.fail("Choose one of your properties for this mortgage.")
        r = app_tables.mortgages.add_row(owner=me, property=prop, created=C.now(), is_demo=bool(prop["is_demo"]), **fields)
    return C.ok(mortgage=mortgage_dict(r))


@anvil.server.callable(require_user=True)
def delete_mortgage(mortgage_id):
    me = C.require_user()
    r = owned(app_tables.mortgages, mortgage_id, me)
    if r is not None:
        r.delete()
    return C.ok()


@anvil.server.callable(require_user=True)
def save_prefs(prefs):
    me = C.require_user()
    prefs = prefs if isinstance(prefs, dict) else {}
    p = prefs_of(me)
    p["currency"] = C.choice(prefs.get("currency"), CURRENCIES, p["currency"])
    p["region"] = C.choice(prefs.get("region"), REGIONS, p["region"])
    p["compounding"] = C.choice(prefs.get("compounding"), COMPOUNDING, p["compounding"])
    me["prefs"] = p
    return C.ok(prefs=p)


@anvil.server.callable(require_user=True)
def load_sample():
    """Fill this landlord's account with the sample portfolio (flagged, so clear_sample removes exactly it)."""
    me = C.require_user()
    if len(app_tables.properties.search(owner=me, is_demo=True)):
        return C.fail("The sample is already in your account.")
    if C.rate_limited("load_sample", 5, 3600):
        return C.fail("Please wait a little before loading the sample again.")
    DemoData.build_portfolio(me, C.name_of(me))
    return C.ok()


@anvil.server.callable(require_user=True)
def clear_sample():
    me = C.require_user()
    DemoData.clear_portfolio(me)
    return C.ok()

