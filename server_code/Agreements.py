"""Condition reports (move-in / move-out) and lease renewal offers, kept INSIDE the sealed record (2026-11-20).

Nothing here has its own table: each report, offer and answer is one Record.append entry with an `event` name and a
body in a fixed, readable shape, so it is dated, sealed by the hash chain and shown in the thread like everything else,
and the live app needed no schema change. summary(entries) reads the entries back into plain dicts.

Events and body shapes (first line is what the thread shows in bold; the rest shows under it):
  report_move_in / report_move_out   "Move-in condition report: 9 rooms checked (7 good, 1 worn, 1 damaged)."
                                     then one line per room "<Room>: <Good|Worn|Damaged|Missing>[ — <note>]"
                                     and optionally "General note: <text>"
  report_agreed / report_disputed    "Agrees with the move-in condition report #12." [+ "\n<note>"]
  renewal_offer                      "Lease renewal offer: ..." + readable lines + "Terms: rent 1850.00 · from 2027-02-01 · until 2028-01-31"
  renewal_accepted / renewal_talk    "Accepts the lease renewal offer #15." / "Would like to talk about the lease renewal offer #15."
  renewal_applied                    "New lease terms from offer #15 are in place: ..."
Either side can write a report; only the other side answers it, once. Offers come from the landlord; the tenant answers;
the landlord applies an accepted offer (rent + lease end change on the tenancy).
"""
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Record

KINDS = {"move_in": "Move-in", "move_out": "Move-out"}
CONDITIONS = ["Good", "Worn", "Damaged", "Missing"]
RANK = {c: i for i, c in enumerate(CONDITIONS)}
REPORT_EVENTS = ("report_move_in", "report_move_out")
ANSWER_EVENTS = ("report_agreed", "report_disputed")
RENEWAL_EVENTS = ("renewal_offer", "renewal_accepted", "renewal_talk", "renewal_applied")
SEP = " — "
_REF = re.compile(r"#(\d+)")


# ------------------------------------------------------------------------------------------------ reading entries back
def _ref(body):
    m = _REF.search((body or "").split("\n")[0])
    return int(m.group(1)) if m else None


def _rest(body):
    parts = (body or "").split("\n", 1)
    return parts[1].strip() if len(parts) > 1 else ""


def parse_report(body):
    rooms, note = [], ""
    for line in (body or "").split("\n")[1:]:
        if line.startswith("General note: "):
            note = line[len("General note: "):].strip()
            continue
        name, colon, rest = line.partition(": ")
        if not colon:
            continue
        cond, _, rnote = rest.partition(SEP)
        cond = cond.strip()
        if cond in RANK:
            rooms.append({"name": name.strip(), "condition": cond, "note": rnote.strip()})
    return rooms, note


def parse_terms(body):
    for line in (body or "").split("\n"):
        if line.startswith("Terms: "):
            out = {}
            for part in line[len("Terms: "):].split(" · "):
                k, _, v = part.strip().partition(" ")
                out[k] = v.strip()
            rent = C.num(out.get("rent"), 0, 1e7, None)
            return {"rent": rent, "old_rent": C.num(out.get("was"), 0, 1e7, None), "from": out.get("from") or "",
                    "until": "" if out.get("until") in (None, "", "open-ended") else out["until"]}
    return None


def _changes(move_in, move_out):
    """Rooms that got worse between the move-in and move-out reports (matched by name, ignoring case)."""
    before = {r["name"].lower(): r for r in move_in["rooms"]}
    out = []
    for r in move_out["rooms"]:
        b = before.get(r["name"].lower())
        if b is None:
            if r["condition"] != "Good":
                out.append({"name": r["name"], "before": "", "after": r["condition"], "note": r["note"]})
        elif RANK[r["condition"]] > RANK[b["condition"]]:
            out.append({"name": r["name"], "before": b["condition"], "after": r["condition"], "note": r["note"]})
    return out


def summary(entries):
    """{reports: [...newest first], renewal: the latest offer with its answer, or None} from Record rows."""
    reports, by_seq, renewal = [], {}, None
    for e in entries:
        ev, body = e["event"] or "", e["body"] or ""
        if ev in REPORT_EVENTS:
            rooms, note = parse_report(body)
            kind = ev[len("report_"):]
            r = {"seq": e["seq"], "kind": kind, "label": KINDS[kind], "author_kind": e["author_kind"],
                 "author_name": e["author_name"] or "", "created": C.iso(e["created"]), "rooms": rooms, "note": note,
                 "counts": {c: len([x for x in rooms if x["condition"] == c]) for c in CONDITIONS},
                 "answer": None, "changes": []}
            reports.append(r)
            by_seq[e["seq"]] = r
        elif ev in ANSWER_EVENTS:
            r = by_seq.get(_ref(body))
            if r is not None and r["answer"] is None and e["author_kind"] != r["author_kind"]:
                r["answer"] = {"agree": ev == "report_agreed", "note": _rest(body), "by": e["author_name"] or "",
                               "author_kind": e["author_kind"], "created": C.iso(e["created"]), "seq": e["seq"]}
        elif ev == "renewal_offer":
            terms = parse_terms(body) or {}
            lines = body.split("\n")
            note = "\n".join(x for x in lines[1:] if x.startswith("Note: "))[len("Note: "):]
            renewal = dict(terms, seq=e["seq"], created=C.iso(e["created"]), by=e["author_name"] or "", note=note,
                           status="sent", answer_note="", answered_at="", answered_by="", applied_at="")
        elif ev in ("renewal_accepted", "renewal_talk", "renewal_applied") and renewal and _ref(body) == renewal["seq"]:
            if ev == "renewal_applied":
                renewal.update(status="applied", applied_at=C.iso(e["created"]))
            elif renewal["status"] == "sent":
                renewal.update(status="accepted" if ev == "renewal_accepted" else "talk", answer_note=_rest(body),
                               answered_at=C.iso(e["created"]), answered_by=e["author_name"] or "")
    move_ins = [r for r in reports if r["kind"] == "move_in"]
    for r in reports:
        if r["kind"] == "move_out":
            earlier = [m for m in move_ins if m["seq"] < r["seq"]]
            if earlier:
                r["changes"] = _changes(earlier[-1], r)
                r["compared_to"] = earlier[-1]["seq"]
    reports.reverse()
    return {"reports": reports, "renewal": renewal}


def renewal_state(entries):
    """Just the latest renewal offer's status, for the portfolio (Home's "needs your attention")."""
    r = summary([e for e in entries if (e["event"] or "") in RENEWAL_EVENTS])["renewal"]
    return {"seq": r["seq"], "status": r["status"], "rent": r["rent"], "from": r["from"], "until": r["until"],
            "by": r["answered_by"]} if r else None


# ------------------------------------------------------------------------------------------------ writing
def _clean_rooms(rooms):
    if not isinstance(rooms, (list, tuple)):
        return None, "Add at least one room."
    out = []
    for r in rooms[:30]:
        if not isinstance(r, dict):
            continue
        name = C.text(r.get("name"), 40).replace(":", "").replace(SEP.strip(), "-").strip()
        if not name or name.lower().startswith("general note"):
            continue
        cond = r.get("condition") if r.get("condition") in RANK else "Good"
        out.append({"name": name, "condition": cond, "note": C.text(r.get("note"), 300).replace(SEP, " - ")})
    if not out:
        return None, "Add at least one room with a name."
    return out, None


def report_body(kind, rooms, note=""):
    counts = [(len([r for r in rooms if r["condition"] == c]), c.lower()) for c in CONDITIONS]
    parts = ", ".join("%d %s" % (n, c) for n, c in counts if n)
    head = "%s condition report: %s checked (%s)." % (KINDS[kind], _plural(len(rooms), "room"), parts)
    lines = [head] + ["%s: %s%s" % (r["name"], r["condition"], (SEP + r["note"]) if r["note"] else "") for r in rooms]
    if note:
        lines.append("General note: " + note)
    return "\n".join(lines)


def _plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def write_report(t, author_kind, author_name, kind, rooms, note=""):
    if kind not in KINDS:
        return C.fail("Choose move-in or move-out.")
    rooms, err = _clean_rooms(rooms)
    if err:
        return C.fail(err)
    note = C.text(note, 600)
    if C.rate_limited("condition_report", 20, 3600):
        return C.fail("That's a lot of reports in one hour. Please try again later.")
    m = Record.append(t, "event", author_kind, author_name, report_body(kind, rooms, note), event="report_" + kind,
                      is_demo=t["is_demo"])
    return C.ok(seq=m["seq"])


def answer_report(t, author_kind, author_name, seq, agree, note=""):
    entries = Record.entries(t)
    rep = next((r for r in summary(entries)["reports"] if r["seq"] == int(C.num(seq, 0, 1e9, 0))), None)
    if rep is None:
        return C.fail("That report isn't in this record.")
    if rep["author_kind"] == author_kind:
        return C.fail("The other side answers a report, not the person who wrote it.")
    if rep["answer"] is not None:
        return C.fail("This report already has an answer.")
    note = C.text(note, 1000, multiline=True)
    if not agree and not note:
        return C.fail("Say what isn't right, so it's on record.")
    body = ("Agrees with" if agree else "Doesn't agree with") + " the %s condition report #%d." % (rep["label"].lower(), rep["seq"])
    if note:
        body += "\n" + note
    Record.append(t, "event", author_kind, author_name, body, event="report_agreed" if agree else "report_disputed",
                  is_demo=t["is_demo"])
    return C.ok()


def _owned_tenancy(tenancy_id):
    me = C.require_user()
    r = C.row_by_id(app_tables.tenancies, tenancy_id)
    return (me, r) if (r is not None and r["owner"] == me) else (me, None)


def _day(d):
    return "%d %s" % (d.day, d.strftime("%b %Y"))


# ------------------------------------------------------------------------------------------------ callables: landlord
@anvil.server.callable(require_user=True)
def landlord_report(tenancy_id, kind, rooms, note=""):
    """The landlord writes a move-in or move-out condition report into the record."""
    me, t = _owned_tenancy(tenancy_id)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    return write_report(t, "landlord", C.name_of(me), kind, rooms, note)


@anvil.server.callable(require_user=True)
def landlord_report_answer(tenancy_id, seq, agree, note=""):
    me, t = _owned_tenancy(tenancy_id)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    return answer_report(t, "landlord", C.name_of(me), seq, bool(agree), note)


@anvil.server.callable(require_user=True)
def send_renewal(tenancy_id, rent, start, until=None, note=""):
    """A lease renewal offer, sealed in the record (the record is the proof the notice was given, and when)."""
    me, t = _owned_tenancy(tenancy_id)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    if t["status"] == "ended":
        return C.fail("This tenancy has ended.")
    new_rent = round(C.num(rent, 0, 1e7, 0) or 0, 2)
    if new_rent <= 0:
        return C.fail("Enter the new monthly rent.")
    start_d = C.date(start)
    if start_d is None:
        return C.fail("Choose the date the new terms start.")
    if start_d < C.now().date():
        return C.fail("The new terms can't start in the past.")
    until_d = C.date(until)
    if until_d is not None and until_d <= start_d:
        return C.fail("The new lease must end after it starts.")
    if C.rate_limited("send_renewal", 20, 3600):
        return C.fail("That's a lot of offers in one hour. Please try again later.")
    from . import Portfolio
    from .Ledger import money
    cur = Portfolio.prefs_of(me)["currency"]
    old = t["rent"] or 0
    change = ((new_rent - old) / old * 100) if old else 0
    lines = ["Lease renewal offer: %s a month from %s, %s." % (
        money(new_rent, cur), _day(start_d), ("lease until " + _day(until_d)) if until_d else "open-ended lease")]
    if old and abs(new_rent - old) >= 0.005:
        lines.append("Rent now %s (%s%.1f%%)." % (money(old, cur), "+" if change > 0 else "−", abs(change)))
    elif old:
        lines.append("Same rent as now.")
    lines.append("Please answer here: accept, or ask to talk.")
    note = C.text(note, 600)
    if note:
        lines.append("Note: " + note)
    lines.append("Terms: rent %.2f · was %.2f · from %s · until %s" % (new_rent, old, start_d.isoformat(),
                                                                    until_d.isoformat() if until_d else "open-ended"))
    m = Record.append(t, "event", "landlord", C.name_of(me), "\n".join(lines), event="renewal_offer", is_demo=t["is_demo"])
    return C.ok(seq=m["seq"])


@anvil.server.callable(require_user=True)
def apply_renewal(tenancy_id, seq):
    """An accepted offer: put its rent and lease end on the tenancy, and say so in the record."""
    me, t = _owned_tenancy(tenancy_id)
    if t is None:
        return C.fail("That tenancy isn't yours.")
    r = summary(Record.entries(t))["renewal"]
    if r is None or r["seq"] != int(C.num(seq, 0, 1e9, 0)):
        return C.fail("That offer isn't the latest one in this record.")
    if r["status"] != "accepted":
        return C.fail("Only an accepted offer can be applied.")
    from . import Portfolio
    from .Ledger import money
    cur = Portfolio.prefs_of(me)["currency"]
    until_d = C.date(r["until"])
    t.update(rent=r["rent"], end_date=until_d)
    if t["status"] == "ended":
        t.update(status="active")
    Record.append(t, "event", "landlord", C.name_of(me), "New lease terms from offer #%d are in place: %s a month from %s, %s." % (
        r["seq"], money(r["rent"], cur), _day(C.date(r["from"]) or C.now().date()),
        ("lease until " + _day(until_d)) if until_d else "open-ended lease"), event="renewal_applied", is_demo=t["is_demo"])
    return C.ok()


# ------------------------------------------------------------------------------------------------ callables: tenant
def _tenancy(token):
    from .TenantPortal import _tenancy as by_token
    return by_token(token)


def _tname(t, name):
    name = C.text(name, 60)
    return name if len(name) >= 2 else t["tenant_name"]


@anvil.server.callable
def tenant_report(token, kind, rooms, note="", name=None):
    """The tenant writes a condition report from their private link (the link is the key)."""
    t = _tenancy(token)
    if t is None:
        return C.fail("This link doesn't work any more. Ask your landlord for the new one.")
    return write_report(t, "tenant", _tname(t, name), kind, rooms, note)


@anvil.server.callable
def tenant_report_answer(token, seq, agree, note="", name=None):
    t = _tenancy(token)
    if t is None:
        return C.fail("This link doesn't work any more. Ask your landlord for the new one.")
    if C.rate_limited("report_answer", 30, 3600):
        return C.fail("Please try again a little later.")
    return answer_report(t, "tenant", _tname(t, name), seq, bool(agree), note)


@anvil.server.callable
def tenant_renewal_answer(token, seq, accept, note="", name=None):
    t = _tenancy(token)
    if t is None:
        return C.fail("This link doesn't work any more. Ask your landlord for the new one.")
    if C.rate_limited("renewal_answer", 20, 3600):
        return C.fail("Please try again a little later.")
    r = summary(Record.entries(t))["renewal"]
    if r is None or r["seq"] != int(C.num(seq, 0, 1e9, 0)):
        return C.fail("That offer isn't the latest one. Reload the page.")
    if r["status"] != "sent":
        return C.fail("This offer already has an answer.")
    note = C.text(note, 1000, multiline=True)
    body = ("Accepts the lease renewal offer #%d." if accept else "Would like to talk about the lease renewal offer #%d.") % r["seq"]
    if note:
        body += "\n" + note
    Record.append(t, "event", "tenant", _tname(t, name), body, event="renewal_accepted" if accept else "renewal_talk",
                  is_demo=t["is_demo"])
    return C.ok()


def demo_story(t, landlord, tenant_first, when, kind="move_in", rooms=None, agree_after=None):
    """DemoData: a sealed condition report (and the tenant's agreement) in the past."""
    rooms = rooms or [{"name": n, "condition": c, "note": x} for n, c, x in DEMO_ROOMS]
    m = Record.append(t, "event", "landlord", landlord, report_body(kind, rooms, "Keys: 2 door, 1 mailbox. Meters read on the day."),
                      event="report_" + kind, is_demo=True, when=when)
    if agree_after:
        Record.append(t, "event", "tenant", tenant_first, "Agrees with the %s condition report #%d." % (KINDS[kind].lower(), m["seq"]),
                      event="report_agreed", is_demo=True, when=when + agree_after)


def demo_offer(t, landlord, tenant_first, when, new_rent, start, until, accept_after=None, currency="CAD"):
    """DemoData: a renewal offer (and an acceptance) in the past."""
    from .Ledger import money
    old = t["rent"] or 0
    body = "\n".join(["Lease renewal offer: %s a month from %s, lease until %s." % (money(new_rent, currency), _day(start), _day(until)),
                      "Rent now %s (+%.1f%%)." % (money(old, currency), (new_rent - old) / old * 100),
                      "Please answer here: accept, or ask to talk.",
                      "Note: Thank you for another great year. Taxes and insurance went up, so a small increase.",
                      "Terms: rent %.2f · was %.2f · from %s · until %s" % (new_rent, old, start.isoformat(), until.isoformat())])
    m = Record.append(t, "event", "landlord", landlord, body, event="renewal_offer", is_demo=True, when=when)
    if accept_after:
        Record.append(t, "event", "tenant", tenant_first, "Accepts the lease renewal offer #%d.\nThanks, happy to stay!" % m["seq"],
                      event="renewal_accepted", is_demo=True, when=when + accept_after)


DEMO_ROOMS = [("Entry", "Good", ""), ("Kitchen", "Good", "New tap, small chip on the counter edge by the stove"),
              ("Living room", "Good", ""), ("Bedroom 1", "Worn", "Two nail holes above the bed"),
              ("Bedroom 2", "Good", ""), ("Bathroom", "Good", "Grout re-sealed last month"),
              ("Windows & blinds", "Worn", "Blind in bedroom 2 sticks"), ("Appliances", "Good", "Fridge, stove, dishwasher all working")]
