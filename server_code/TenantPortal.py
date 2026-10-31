"""The tenant's side: a private link (#t/<token>), no account needed.

Anyone holding the link can read the record and write in it, so the landlord shares it only with the
tenant and can make a new one (reset_link) if it leaks. Tenants never see the landlord's email or numbers
beyond their own rent.
"""
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import common as C
from . import Record, Tenancy

BAD_LINK = "This link doesn't work any more. Ask your landlord for the new one."


def _tenancy(token):
    token = C.text(token, 60)
    if len(token) < 8:
        return None
    try:
        return app_tables.tenancies.get(token=token)
    except Exception:
        return None


def _name(t, name):
    name = C.text(name, 60)
    return name if len(name) >= 2 else t["tenant_name"]


@anvil.server.callable
def tenant_view(token, mark_seen=True):
    from . import DemoData
    DemoData.ensure_loaded()
    t = _tenancy(token)
    if t is None:
        return C.fail(BAD_LINK)
    entries = Record.entries(t)
    if mark_seen:
        t.update(tenant_seen=entries[-1]["seq"] if entries else 0, tenant_last_visit=C.now())
    p, owner = t["property"], t["owner"]
    from . import Portfolio
    return C.ok(
        tenancy={"unit": t["unit"] or "", "tenant_name": t["tenant_name"], "rent": t["rent"] or 0,
                 "due_day": int(t["due_day"] or 1), "deposit": t["deposit"] or 0, "start_date": C.iso(t["start_date"]),
                 "end_date": C.iso(t["end_date"]), "status": t["status"], "demo": bool(t["is_demo"])},
        property={"name": p["name"], "address": p["address"] or "", "door": p["door"] or "red"},
        landlord_name=C.name_of(owner), currency=Portfolio.prefs_of(owner)["currency"],
        entries=[Record.entry_dict(e) for e in entries],
        tasks=[_task(k) for k in app_tables.tasks.search(tables.order_by("number", ascending=False), tenancy=t)],
        rent_payments=Tenancy.rent_payments(t), stats=Tenancy.response_stats(owner), seal=Record.verify(t))


def _task(k):
    d = Tenancy.task_dict(k)
    d.pop("cost", None)  # the landlord's costs are theirs
    return d


@anvil.server.callable
def tenant_post(token, name, body):
    t = _tenancy(token)
    if t is None:
        return C.fail(BAD_LINK)
    body = C.text(body, 4000, multiline=True)
    if not body:
        return C.fail("Write a message first.")
    if C.rate_limited("tenant_post", 40, 3600):
        return C.fail("That's a lot of messages in one hour. Please try again a little later.")
    r = Record.append(t, "message", "tenant", _name(t, name), body, is_demo=t["is_demo"])
    t["tenant_seen"] = r["seq"]
    return C.ok(entry=Record.entry_dict(r))


@anvil.server.callable
def tenant_request(token, name, title, details="", category="other", priority="normal"):
    t = _tenancy(token)
    if t is None:
        return C.fail(BAD_LINK)
    f, err = Tenancy.clean_task_input(title, details, category, priority)
    if err:
        return C.fail(err)
    if C.rate_limited("tenant_request", 12, 3600):
        return C.fail("That's a lot of requests in one hour. Please try again a little later.")
    k = Tenancy.create_task(t, "tenant", _name(t, name), f["title"], f["details"], f["category"], f["priority"])
    return C.ok(task=_task(k))


@anvil.server.callable
def tenant_confirm(token, task_id, fixed, name=None, note=None):
    """After the landlord marks a task done: the tenant confirms it's fixed, or says it isn't (reopens it)."""
    t = _tenancy(token)
    if t is None:
        return C.fail(BAD_LINK)
    k = C.row_by_id(app_tables.tasks, task_id)
    if k is None or k["tenancy"] != t:
        return C.fail("That request isn't part of this tenancy.")
    if k["status"] != "done":
        return C.fail("You can confirm a request once it's marked done.")
    if C.rate_limited("tenant_confirm", 30, 3600):
        return C.fail("Please try again a little later.")
    note = C.text(note, 1000, multiline=True)
    who = _name(t, name)
    when = C.now().replace(microsecond=0)
    if fixed:
        k.update(confirmed_at=when, updated=when)
        body, event = "Confirmed #%d %s is fixed." % (k["number"], k["title"]), "confirmed"
    else:
        k.update(status="requested", done_at=None, confirmed_at=None, updated=when)
        body, event = "Says #%d %s isn't fixed yet." % (k["number"], k["title"]), "reopened"
    Record.append(t, "event", "tenant", who, body + ("\n" + note if note else ""), task=k, event=event,
                  is_demo=t["is_demo"], when=when)
    return C.ok(task=_task(k))
