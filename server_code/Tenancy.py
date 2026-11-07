"""Tenancies (who rents what), the landlord's side of the permanent record, and repair/task requests.

A tenancy has a private link (token) for the tenant: see TenantPortal.py for their side.
Messages are never edited or deleted. Task changes are written into the record as events, with dates.
"""
import secrets
import statistics

import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import common as C
from . import Record
from .Ledger import money

STATUSES = ["requested", "acknowledged", "scheduled", "in_progress", "done", "declined"]
TASK_CATEGORIES = ["plumbing", "heating", "electrical", "appliance", "doors_windows", "pests", "outdoor", "safety",
                   "cleaning", "other"]
PRIORITIES = ["low", "normal", "urgent"]
ORDER = {s: i for i, s in enumerate(STATUSES)}


def new_token():
    return secrets.token_urlsafe(18)


def _owned(table, row_id, me):
    r = C.row_by_id(table, row_id)
    return r if (r is not None and r["owner"] == me) else None


def where(t):
    p = t["property"]
    return p["name"] + (" · " + t["unit"] if t["unit"] else "")


def task_dict(r):
    t = r["tenancy"]
    days = None
    if r["requested_at"] is not None:
        end = r["done_at"] or C.now()
        days = round((end - r["requested_at"]).total_seconds() / 86400.0, 1)
    return {"id": r.get_id(), "number": int(r["number"] or 0), "tenancy_id": t.get_id() if t is not None else None,
            "property_id": r["property"].get_id() if r["property"] is not None else None,
            "where": where(t) if t is not None else "", "tenant_name": t["tenant_name"] if t is not None else "",
            "title": r["title"], "details": r["details"] or "", "category": r["category"] or "other",
            "priority": r["priority"] or "normal", "status": r["status"], "requested_by": r["requested_by"],
            "requested_name": r["requested_name"] or "", "requested_at": C.iso(r["requested_at"]),
            "acknowledged_at": C.iso(r["acknowledged_at"]), "scheduled_for": C.iso(r["scheduled_for"]),
            "started_at": C.iso(r["started_at"]), "done_at": C.iso(r["done_at"]), "confirmed_at": C.iso(r["confirmed_at"]),
            "cost": r["cost"], "updated": C.iso(r["updated"]), "days_open": days}


def response_stats(owner):
    """Median hours to first response and days to fix, over tenant requests. Shown to both sides."""
    reply, fix, total, answered = [], [], 0, 0
    for t in app_tables.tasks.search(owner=owner, requested_by="tenant"):
        total += 1
        if t["acknowledged_at"] is not None and t["requested_at"] is not None:
            answered += 1
            reply.append((t["acknowledged_at"] - t["requested_at"]).total_seconds() / 3600.0)
        if t["done_at"] is not None and t["requested_at"] is not None:
            fix.append((t["done_at"] - t["requested_at"]).total_seconds() / 86400.0)
    return {"requests": total, "answered": answered,
            "reply_hours": round(statistics.median(reply), 1) if reply else None,
            "fix_days": round(statistics.median(fix), 1) if fix else None}


def create_task(tenancy, by, name, title, details, category, priority, when=None):
    """by: tenant | landlord. Adds the task and its 'requested' event to the record."""
    number = len(app_tables.tasks.search(tenancy=tenancy)) + 1
    at = (when or C.now()).replace(microsecond=0)
    task = app_tables.tasks.add_row(owner=tenancy["owner"], tenancy=tenancy, property=tenancy["property"], number=number,
                                    title=title, details=details, category=category, priority=priority,
                                    status="requested", requested_by=by, requested_name=name, requested_at=at,
                                    updated=at, is_demo=bool(tenancy["is_demo"]))
    body = "Asked for #%d: %s%s%s" % (number, title, " (urgent)" if priority == "urgent" else "",
                                      ("\n" + details) if details else "")
    Record.append(tenancy, "event", by, name, body, task=task, event="requested", is_demo=tenancy["is_demo"], when=at)
    return task


def clean_task_input(title, details, category, priority):
    title = C.text(title, 120)
    if len(title) < 3:
        return None, "Say what needs doing (at least 3 characters)."
    return {"title": title, "details": C.text(details, 3000, multiline=True),
            "category": C.choice(category, TASK_CATEGORIES, "other"),
            "priority": C.choice(priority, PRIORITIES, "normal")}, None


# ------------------------------------------------------------------------------------------------ tenancies
@anvil.server.callable(require_user=True)
def save_tenancy(data):
    me = C.require_user()
    if not isinstance(data, dict):
        return C.fail("Something was missing. Please try again.")
    name = C.text(data.get("tenant_name"), 80)
    if len(name) < 2:
        return C.fail("Enter the tenant's name.")
    email = C.text(data.get("tenant_email"), 120)
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        return C.fail("That email address doesn't look right.")
    fields: dict = {"unit": C.text(data.get("unit"), 40), "tenant_name": name, "tenant_email": email,
              "rent": round(C.num(data.get("rent"), 0, 1e7, 0), 2), "due_day": int(C.num(data.get("due_day"), 1, 28, 1)),
              "deposit": round(C.num(data.get("deposit"), 0, 1e7, 0), 2),
              "start_date": C.date(data.get("start_date"), C.now().date()), "end_date": C.date(data.get("end_date"))}
    if fields["end_date"] is not None and fields["end_date"] < fields["start_date"]:
        return C.fail("The lease can't end before it starts.")
    from . import Portfolio
    cur = Portfolio.prefs_of(me)["currency"]
    if data.get("id"):
        t = _owned(app_tables.tenancies, data["id"], me)
        if t is None:
            return C.fail("That tenancy isn't yours.")
        old_rent = t["rent"] or 0
        t.update(**fields)
        if abs(old_rent - fields["rent"]) >= 0.005:
            Record.append(t, "event", "landlord", C.name_of(me), "Rent changed from %s to %s a month." % (
                money(old_rent, cur), money(fields["rent"], cur)), event="rent_changed",
                is_demo=t["is_demo"])
    else:
        prop = _owned(app_tables.properties, data.get("property_id"), me)
        if prop is None:
            return C.fail("Choose one of your properties.")
        if C.rate_limited("add_tenancy", 40, 3600):
            return C.fail("That's a lot of tenancies in one hour. Please try again later.")
        t = app_tables.tenancies.add_row(owner=me, property=prop, status="active", token=new_token(), landlord_seen=0,
                                         tenant_seen=0, created=C.now(), is_demo=bool(prop["is_demo"]), **fields)
        Record.append(t, "event", "system", "Good Landlord",
                      "Record opened for %s at %s. Rent %s a month, due on day %d. Everything written here is kept "
                      "for good: nobody can edit or delete it." % (name, where(t), money(fields["rent"], cur),
                                                                  fields["due_day"]),
                      event="opened", is_demo=t["is_demo"])
        t["landlord_seen"] = 1
    from .Portfolio import tenancy_dict
    return C.ok(tenancy=tenancy_dict(t))


@anvil.server.callable(require_user=True)
def end_tenancy(tenancy_id, end_date=None):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    if t["status"] == "ended":
        return C.ok()
    day = C.date(end_date, C.now().date())
    t.update(status="ended", end_date=day)
    Record.append(t, "event", "landlord", C.name_of(me), "Ended the tenancy on %s. The record stays readable by both "
                  "sides, and the tenant can still write here." % day.isoformat(), event="ended", is_demo=t["is_demo"])
    return C.ok()


@anvil.server.callable(require_user=True)
def reopen_tenancy(tenancy_id):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    if t["status"] != "ended":
        return C.ok()
    t.update(status="active", end_date=None)
    Record.append(t, "event", "landlord", C.name_of(me), "Reopened the tenancy.", event="reopened", is_demo=t["is_demo"])
    return C.ok()


@anvil.server.callable(require_user=True)
def delete_tenancy(tenancy_id):
    """Only a mistake nobody has used yet: no tenant visit, nothing in the record but its opening line."""
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.ok()
    if t["tenant_last_visit"] is not None or Record.last_seq(t) > 1 or len(app_tables.tasks.search(tenancy=t)) \
            or len(app_tables.ledger.search(tenancy=t)):
        return C.fail("This record has been used, so it's kept for good. You can end the tenancy instead.")
    for m in app_tables.messages.search(tenancy=t):
        m.delete()
    t.delete()
    return C.ok()


@anvil.server.callable(require_user=True)
def reset_link(tenancy_id):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    t["token"] = new_token()
    Record.append(t, "event", "landlord", C.name_of(me), "Made a new private link for the tenant. The old link no "
                  "longer works.", event="link_reset", is_demo=t["is_demo"])
    return C.ok(token=t["token"])


@anvil.server.callable(require_user=True)
def get_tenancy(tenancy_id):
    """The landlord's view of one record: the thread, the tasks, the seal check. Marks it as read."""
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours, or it doesn't exist.")
    from . import Portfolio
    entries = Record.entries(t)
    if entries:
        t["landlord_seen"] = entries[-1]["seq"]
    tasks = [task_dict(k) for k in app_tables.tasks.search(tables.order_by("number", ascending=False), tenancy=t)]
    p = t["property"]
    return C.ok(tenancy=Portfolio.tenancy_dict(t), property={"id": p.get_id(), "name": p["name"], "address": p["address"] or ""},
                entries=[Record.entry_dict(e) for e in entries], tasks=tasks, seal=Record.verify(t),
                prefs=Portfolio.prefs_of(me), landlord_name=C.name_of(me),
                rent_payments=rent_payments(t))


def rent_payments(t):
    return [{"month": e["rent_month"], "amount": e["amount"], "date": C.iso(e["date"])}
            for e in app_tables.ledger.search(tables.order_by("rent_month", ascending=False), tenancy=t, category="rent")]


@anvil.server.callable(require_user=True)
def landlord_post(tenancy_id, body):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    body = C.text(body, 4000, multiline=True)
    if not body:
        return C.fail("Write a message first.")
    if C.rate_limited("landlord_post", 120, 3600):
        return C.fail("That's a lot of messages in one hour. Please slow down a little.")
    r = Record.append(t, "message", "landlord", C.name_of(me), body, is_demo=t["is_demo"])
    t["landlord_seen"] = r["seq"]
    return C.ok(entry=Record.entry_dict(r))


@anvil.server.callable(require_user=True)
def verify_record(tenancy_id):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    return C.ok(seal=Record.verify(t))


# ------------------------------------------------------------------------------------------------ tasks
@anvil.server.callable(require_user=True)
def landlord_new_task(tenancy_id, title, details="", category="other", priority="normal"):
    me = C.require_user()
    t = _owned(app_tables.tenancies, tenancy_id, me)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    f, err = clean_task_input(title, details, category, priority)
    if err:
        return C.fail(err)
    if C.rate_limited("new_task", 60, 3600):
        return C.fail("That's a lot of tasks in one hour. Please try again later.")
    task = create_task(t, "landlord", C.name_of(me), f["title"], f["details"], f["category"], f["priority"])
    task["acknowledged_at"] = task["requested_at"]
    return C.ok(task=task_dict(task))


@anvil.server.callable(require_user=True)
def set_task_status(task_id, status, scheduled_for=None, note=None, cost=None):
    """Move a task along. Every move is written into the record with its date; going back is allowed (and recorded)."""
    me = C.require_user()
    k = _owned(app_tables.tasks, task_id, me)
    if k is None:
        return C.fail("That task isn't yours.")
    if status not in STATUSES:
        return C.fail("Pick a status.")
    note = C.text(note, 1000, multiline=True)
    when = C.now().replace(microsecond=0)
    day = C.date(scheduled_for)
    if status == "scheduled" and day is None:
        return C.fail("Pick the day it's scheduled for.")
    if status == "declined" and len(note) < 3:
        return C.fail("Say why you're declining, so the record is clear.")
    old = k["status"]
    if old == status and status != "scheduled":
        return C.ok(task=task_dict(k))
    ch = {"status": status, "updated": when}
    if ORDER[status] >= ORDER["acknowledged"] and k["acknowledged_at"] is None:
        ch["acknowledged_at"] = when
    if status == "scheduled":
        ch["scheduled_for"] = day
    if status == "in_progress" and k["started_at"] is None:
        ch["started_at"] = when
    if status == "done":
        ch["done_at"] = when
    elif old == "done":
        ch["done_at"] = None
        ch["confirmed_at"] = None
    k.update(**ch)
    label = Record.STATUS_LABELS[status]
    body = "Moved #%d %s to %s" % (k["number"], k["title"], label)
    if status == "scheduled":
        body += " for %s" % day.isoformat()
    body += "." + ("\n" + note if note else "")
    t = k["tenancy"]
    Record.append(t, "event", "landlord", C.name_of(me), body, task=k, event=status, is_demo=t["is_demo"], when=when)
    if status == "done":
        amount = C.num(cost, 0, 1e8, None)
        if amount:
            _record_cost(me, k, amount)
    return C.ok(task=task_dict(k))


def _record_cost(me, k, amount):
    """A finished repair's cost goes into the ledger as a claimable repair (one entry per task)."""
    k["cost"] = round(amount, 2)
    e = app_tables.ledger.get(task=k)
    if e is None:
        app_tables.ledger.add_row(owner=me, property=k["property"], tenancy=k["tenancy"], task=k, kind="expense",
                                  category="repairs", amount=round(amount, 2), date=C.now().date(),
                                  memo="#%d %s" % (k["number"], k["title"]), created=C.now(), is_demo=bool(k["is_demo"]))
    else:
        e["amount"] = round(amount, 2)
