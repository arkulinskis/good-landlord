"""Demo content, so the app never looks empty.

Two kinds:
  - the public demo: a fictional landlord (Maya Chen) with a portfolio, whose first tenancy has the fixed link
    #t/demo-upstairs, so anyone can see the tenant side from the landing page. Loaded on first visit
    (ensure_loaded), removed or reloaded from Admin -> Demo data.
  - a sample portfolio inside a signed-in landlord's own account (Home -> "Explore with a sample"), built by
    the same build_portfolio(), flagged is_demo=True so "Clear the sample" removes exactly it.

Every demo row is flagged is_demo=True; rows created later under a demo property or tenancy inherit the flag.
"""
import datetime as dt
import random

from anvil.tables import app_tables

from . import common as C
from . import Record

DEMO_LANDLORD = ("Maya Chen", "maya.demo@example.com")
PUBLIC_TOKENS = ["demo-upstairs", "demo-garden", "demo-harbour", "demo-willow"]
# Children before parents.
DEMO_TABLES = ["messages", "ledger", "tasks", "tenancies", "mortgages", "properties"]


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    if state() == "never":
        load()


def load():
    remove(remember=False)
    name, email = DEMO_LANDLORD
    u = app_tables.users.get(email=email) or app_tables.users.add_row(email=email, enabled=False)
    u.update(display_name=name, is_demo=True, signed_up=C.now() - dt.timedelta(days=400),
             prefs={"currency": "CAD", "region": "ca", "compounding": "semiannual"})
    build_portfolio(u, name, tokens=PUBLIC_TOKENS)
    C.set_setting("demo", "loaded")
    return counts()


def remove(remember=True):
    for name in DEMO_TABLES:
        for r in getattr(app_tables, name).search(is_demo=True):
            r.delete()
    for u in app_tables.users.search(is_demo=True):
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"users": len(app_tables.users.search(is_demo=True))}
    for name in DEMO_TABLES:
        out[name] = len(getattr(app_tables, name).search(is_demo=True))
    return out


def clear_portfolio(owner):
    """Remove one landlord's sample rows (not the public demo, not their own data)."""
    for name in DEMO_TABLES:
        table = getattr(app_tables, name)
        rows = table.search(is_demo=True) if name == "messages" else table.search(is_demo=True, owner=owner)
        for r in list(rows):
            if name == "messages" and r["tenancy"]["owner"] != owner:
                continue
            r.delete()


# ------------------------------------------------------------------------------------------- the sample portfolio
PROPERTIES = [
    dict(key="maple", name="Maple Row Duplex", address="214 Maple Row", kind="duplex", units=2, purchase_price=545000,
         bought_days=1810, down_payment=109000, closing_costs=11200, improvements=18500, current_value=655000,
         appreciation=3.5, selling_pct=5, door="red",
         notes="Upper and garden-level units. Furnace replaced 2022, roof is original (about 2009)."),
    dict(key="harbour", name="Harbour Lofts 602", address="602 - 88 Harbour Street", kind="condo", units=1,
         purchase_price=398000, bought_days=1290, down_payment=79600, closing_costs=7400, improvements=3200,
         current_value=405000, appreciation=2.5, selling_pct=5, door="blue",
         notes="Condo fees include heat and water. Special assessment rumoured for the elevators."),
    dict(key="willow", name="Willow Lane Cottage", address="38 Willow Lane", kind="cottage", units=1,
         purchase_price=312000, bought_days=3740, down_payment=62400, closing_costs=6100, improvements=24000,
         current_value=520000, appreciation=4, selling_pct=5, door="sage",
         notes="Small yard, detached garage the tenants use for bikes."),
]
MORTGAGES = {
    # key: (lender, share of price borrowed, rate, amortisation, term, days after purchase it started)
    "maple": ("Northbank", 0.8, 2.49, 25, 5, 16),
    "harbour": ("Cedar Credit Union", 0.8, 5.29, 25, 5, 11),
    "willow": ("Northbank", 0.8, 2.69, 25, 10, 31),
}
TENANCIES = [
    # (property key, unit, tenant, email, rent, due day, deposit, started days ago)
    ("maple", "Upstairs", "Jonah & Priya Patel", "patel.demo@example.com", 1850, 1, 1850, 1340),
    ("maple", "Garden level", "Lucie Tremblay", "", 1425, 1, 0, 850),
    ("harbour", "", "Sam Okafor", "sam.demo@example.com", 2150, 1, 2150, 1230),
    ("willow", "", "Minh & Hoa Nguyen", "", 2050, 15, 2050, 2250),
]
# Recurring costs: (property key, category, amount, every n months, month offset, memo)
COSTS = [
    ("maple", "property_tax", 1390, 3, 1, "Municipal tax instalment"),
    ("maple", "insurance", 2280, 12, 3, "Landlord insurance renewal"),
    ("maple", "utilities", 96, 1, 0, "Water"),
    ("maple", "wages", 380, 12, 11, "Snow removal contract"),
    ("harbour", "condo_fees", 410, 1, 0, "Condo fees"),
    ("harbour", "property_tax", 840, 3, 2, "Municipal tax instalment"),
    ("harbour", "insurance", 690, 12, 6, "Condo unit-owner insurance"),
    ("willow", "property_tax", 1020, 3, 0, "Municipal tax instalment"),
    ("willow", "insurance", 1540, 12, 8, "Landlord insurance renewal"),
]
ONE_OFF = [
    # (property key, category, amount, days ago, memo)
    ("maple", "professional", 650, 205, "Accountant: last year's rental return"),
    ("maple", "repairs", 340, 120, "Repaint garden-level bedroom between tenants"),
    ("maple", "advertising", 89, 360, "Listing: parking spot for rent"),
    ("harbour", "repairs", 220, 60, "Replace bathroom exhaust fan"),
    ("harbour", "management", 120, 300, "Rent collection software, yearly"),
    ("willow", "capital", 14800, 340, "New roof (capital improvement)"),
    ("willow", "repairs", 460, 95, "Fence repair after storm"),
    ("willow", "travel", 42, 95, "Two trips to oversee the fence repair"),
    ("willow", "interest_other", 36, 30, "Bank charges"),
]


def _months_back(today, n):
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def build_portfolio(owner, owner_name, tokens=None):
    from . import Tenancy
    rnd = random.Random(7)
    now = C.now().replace(microsecond=0)
    today = now.date()
    props = {}
    for d in PROPERTIES:
        f: dict = {k: v for k, v in d.items() if k not in ("key", "bought_days")}
        props[d["key"]] = app_tables.properties.add_row(
            owner=owner, purchase_date=today - dt.timedelta(days=float(d["bought_days"])), value_date=today - dt.timedelta(days=40),
            archived=False, created=now - dt.timedelta(days=float(d["bought_days"])), is_demo=True, **f)
    for key, (lender, share, rate, amort, term, after) in MORTGAGES.items():
        p = props[key]
        app_tables.mortgages.add_row(owner=owner, property=p, lender=lender, amount=float(round(p["purchase_price"] * share)),
                                     rate=rate, amort_years=amort, term_years=term,
                                     start_date=p["purchase_date"] + dt.timedelta(days=after), frequency="monthly",
                                     compounding="semiannual", created=now, is_demo=True)
    tens = []
    for i, (key, unit, name, email, rent, due, dep, ago) in enumerate(TENANCIES):
        if i == 1:  # Lucie pays a few days late this month (the rent roll shows it, her message explains it)
            due = max(1, min(28, today.day - 3))
        token = tokens[i] if tokens else Tenancy.new_token()
        t = app_tables.tenancies.add_row(owner=owner, property=props[key], unit=unit, tenant_name=name,
                                         tenant_email=email, rent=rent, due_day=due, deposit=dep,
                                         start_date=today - dt.timedelta(days=ago), status="active", token=token,
                                         landlord_seen=0, tenant_seen=0, tenant_last_visit=now - dt.timedelta(hours=3 + i * 5),
                                         created=now - dt.timedelta(days=ago), is_demo=True)
        tens.append(t)

    # 14 months of rent and costs. The current month: Lucie hasn't paid yet (the rent roll shows it as due).
    months = _months_back(today, 14)
    for (y, m) in months:
        ym = "%d-%02d" % (y, m)
        for i, t in enumerate(tens):
            due = dt.date(y, m, min(int(t["due_day"]), 28))
            if due > today or (ym == today.strftime("%Y-%m") and i == 1):
                continue
            paid = due + dt.timedelta(days=rnd.choice([0, 0, 0, 1, 2, -1]))
            app_tables.ledger.add_row(owner=owner, property=t["property"], tenancy=t, kind="income", category="rent",
                                      amount=float(t["rent"]), date=min(paid, today), memo="Rent %s" % _month_name(y, m),
                                      rent_month=ym, created=now, is_demo=True)
        for (key, cat, amount, every, offset, memo) in COSTS:
            if (m + offset) % every:
                continue
            day = dt.date(y, m, min(5 + offset, 28))
            if day > today:
                continue
            jitter = 1 + rnd.uniform(-.08, .08) if cat == "utilities" else 1
            app_tables.ledger.add_row(owner=owner, property=props[key], kind="expense", category=cat,
                                      amount=round(amount * jitter, 2), date=day, memo=memo, created=now, is_demo=True)
    for (key, cat, amount, ago, memo) in ONE_OFF:
        app_tables.ledger.add_row(owner=owner, property=props[key], kind="expense", category=cat, amount=float(amount),
                                  date=today - dt.timedelta(days=ago), memo=memo, created=now, is_demo=True)
    app_tables.ledger.add_row(owner=owner, property=props["maple"], tenancy=tens[0], kind="income", category="parking",
                              amount=60.0, date=today - dt.timedelta(days=12), memo="Second parking spot", created=now,
                              is_demo=True)
    # Conversations happen in the afternoon (UTC), not at whatever time the demo was loaded.
    story_now = now.replace(hour=17, minute=12)
    if story_now > now:
        story_now -= dt.timedelta(days=1)
    _stories(owner, owner_name, tens, story_now)


def _month_name(y, m):
    from .Ledger import MONTHS
    return "%s %d" % (MONTHS[m - 1], y)


def _stories(owner, landlord, tens, now):
    """Conversations and requests, written through the same sealed record as real ones."""
    from . import Tenancy
    H = dt.timedelta(hours=1)
    D = dt.timedelta(days=1)

    def opened(t, at):
        Record.append(t, "event", "system", "Good Landlord",
                      "Record opened for %s at %s. Everything written here is kept for good: nobody can edit or "
                      "delete it." % (t["tenant_name"], Tenancy.where(t)), event="opened", is_demo=True, when=at)

    def first(t):
        return t["tenant_name"].split(" ")[0]

    def msg(t, at, who, body):
        kind, name = ("landlord", landlord) if who == "L" else ("tenant", first(t))
        Record.append(t, "message", kind, name, body, is_demo=True, when=at)

    def task(t, at, by, title, details, cat, prio):
        return Tenancy.create_task(t, by, landlord if by == "landlord" else first(t), title, details, cat, prio, when=at)

    def move(t, k, at, status, note="", day=None, cost=None):
        ch = {"status": status, "updated": at}
        if k["acknowledged_at"] is None:
            ch["acknowledged_at"] = at
        if status == "scheduled":
            ch["scheduled_for"] = day
        if status == "in_progress" and k["started_at"] is None:
            ch["started_at"] = at
        if status == "done":
            ch["done_at"] = at
        if cost:
            ch["cost"] = float(cost)
        k.update(**ch)
        body = "Moved #%d %s to %s" % (k["number"], k["title"], Record.STATUS_LABELS[status])
        body += (" for %s" % day.isoformat() if day else "") + "." + ("\n" + note if note else "")
        Record.append(t, "event", "landlord", landlord, body, task=k, event=status, is_demo=True, when=at)
        if cost:
            app_tables.ledger.add_row(owner=owner, property=k["property"], tenancy=t, task=k, kind="expense",
                                      category="repairs", amount=float(cost), date=at.date(),
                                      memo="#%d %s" % (k["number"], k["title"]), created=at, is_demo=True)

    def confirm(t, k, at):
        k.update(confirmed_at=at)
        Record.append(t, "event", "tenant", first(t), "Confirmed #%d %s is fixed." % (k["number"], k["title"]),
                      task=k, event="confirmed", is_demo=True, when=at)

    # Upstairs: the Patels
    t = tens[0]
    start = now - 46 * D
    opened(t, start)
    msg(t, start + 2 * H, "L", "Welcome to our shared record! Anything about the apartment can go here, and it stays here for both of us.")
    msg(t, start + 5 * H, "T", "Great, thanks Maya. Much easier than digging through texts.")
    k = task(t, now - 40 * D, "tenant", "Kitchen tap drips", "The hot side drips about once a second, even when fully closed.", "plumbing", "normal")
    move(t, k, now - 40 * D + 3 * H, "acknowledged", "Thanks for flagging. I'll call the plumber tomorrow.")
    move(t, k, now - 39 * D, "scheduled", "Plumber (Flow Bros) comes between 9 and 11.", day=(now - 37 * D).date())
    move(t, k, now - 37 * D + 2 * H, "done", "Cartridge replaced.", cost=145)
    confirm(t, k, now - 37 * D + 8 * H)
    msg(t, now - 20 * D, "T", "Heads-up: we'll be away 12 to 19 next month. A neighbour has a key if anything comes up.")
    msg(t, now - 20 * D + 4 * H, "L", "Thanks for letting me know. Have a good trip!")
    k = task(t, now - 6 * D, "tenant", "Smoke alarm keeps chirping", "Hallway alarm chirps every minute. We changed the battery but it continues.", "safety", "urgent")
    move(t, k, now - 6 * D + 1 * H, "acknowledged", "Safety first: I'll bring a new alarm tonight.")
    move(t, k, now - 6 * D + 2 * H, "in_progress")
    task(t, now - 1 * D, "tenant", "Bathroom fan is noisy", "It rattles loudly for the first minute after switching on.", "electrical", "low")
    t["landlord_seen"] = Record.last_seq(t) - 1
    t["tenant_seen"] = Record.last_seq(t)

    # Garden level: Lucie
    t = tens[1]
    opened(t, now - 70 * D)
    k = task(t, now - 64 * D, "tenant", "Bedroom window won't latch", "", "doors_windows", "normal")
    move(t, k, now - 63 * D, "scheduled", day=(now - 60 * D).date())
    move(t, k, now - 60 * D + 3 * H, "done", "New latch fitted.", cost=65)
    confirm(t, k, now - 59 * D)
    msg(t, now - 9 * D, "L", "Snow removal starts on December 1st this year. The contractor will also do the side path to your door.")
    msg(t, now - 2 * D, "T", "Hi Maya, could I keep my bike in the shed over the winter?")
    msg(t, now - 2 * D + 20 * dt.timedelta(minutes=1), "T", "Also: my rent for this month will be 3 days late, sorry! Paycheque timing.")
    t["landlord_seen"] = Record.last_seq(t) - 2
    t["tenant_seen"] = Record.last_seq(t)

    # Harbour: Sam
    t = tens[2]
    opened(t, now - 100 * D)
    k = task(t, now - 3 * D, "tenant", "Dishwasher won't drain", "Water stays at the bottom after every cycle. I cleaned the filter.", "appliance", "normal")
    move(t, k, now - 3 * D + 5 * H, "acknowledged")
    move(t, k, now - 2 * D, "scheduled", "Appliance repair visit; you don't need to be home, I'll let them in.", day=(now + 2 * D).date())
    msg(t, now - 2 * D + 1 * H, "T", "Perfect, thanks!")
    t["landlord_seen"] = Record.last_seq(t)
    t["tenant_seen"] = Record.last_seq(t)

    # Willow: the Nguyens
    t = tens[3]
    opened(t, now - 200 * D)
    k = task(t, now - 33 * D, "landlord", "Annual furnace service", "Yearly check before winter.", "heating", "normal")
    move(t, k, now - 33 * D + H, "scheduled", "Technician comes in the morning.", day=(now - 26 * D).date())
    move(t, k, now - 26 * D + 4 * H, "done", "Serviced, filter replaced. All good.", cost=189)
    msg(t, now - 26 * D + 6 * H, "T", "The technician was very nice. Thank you!")
    k = task(t, now - 8 * D, "landlord", "Clean the gutters", "Before the snow.", "outdoor", "low")
    move(t, k, now - 8 * D + H, "scheduled", day=(now + 5 * D).date())
    t["landlord_seen"] = Record.last_seq(t)
    t["tenant_seen"] = Record.last_seq(t) - 1
