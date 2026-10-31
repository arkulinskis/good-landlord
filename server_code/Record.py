"""The tenancy record: every message and every task change between a landlord and a tenant, in order.

Entries are append-only. No server function edits or deletes a message (only Admin -> Demo data removes
demo rows). Each entry is sealed with a SHA-256 hash of its content plus the previous entry's hash, so
changing or removing any entry later breaks the chain, and verify() says where.
"""
import hashlib

import anvil.tables as tables
from anvil.tables import app_tables

from . import common as C

GENESIS = "good-landlord-record-v1"
STATUS_LABELS = {"requested": "Requested", "acknowledged": "Seen", "scheduled": "Scheduled",
                 "in_progress": "In progress", "done": "Done", "declined": "Declined"}


def _stamp(t):
    return C.iso(t.replace(microsecond=0))


def _digest(prev, seq, created, author_kind, author_name, body, event, task_no):
    raw = "|".join([prev, str(int(seq)), _stamp(created), author_kind or "", author_name or "", body or "",
                    event or "", str(int(task_no)) if task_no else ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def entries(tenancy):
    return list(app_tables.messages.search(tables.order_by("seq"), tenancy=tenancy))


@tables.in_transaction
def append(tenancy, kind, author_kind, author_name, body, task=None, event=None, is_demo=False, when=None):
    """Add one sealed entry. kind: message | event. author_kind: landlord | tenant | system."""
    last = None
    for r in app_tables.messages.search(tables.order_by("seq", ascending=False), tenancy=tenancy):
        last = r
        break
    seq = (last["seq"] if last else 0) + 1
    prev = last["hash"] if last else GENESIS
    created = (when or C.now()).replace(microsecond=0)
    task_no = task["number"] if task is not None else None
    h = _digest(prev, seq, created, author_kind, author_name, body, event, task_no)
    return app_tables.messages.add_row(tenancy=tenancy, seq=seq, kind=kind, author_kind=author_kind,
                                       author_name=author_name, body=body, task=task, event=event, created=created,
                                       prev_hash=prev, hash=h, is_demo=bool(is_demo))


def verify(tenancy):
    """Recompute the chain. {intact, count, head, broken_at}"""
    prev, n = GENESIS, 0
    for r in entries(tenancy):
        n += 1
        task_no = r["task"]["number"] if r["task"] is not None else None
        good = (r["seq"] == n and r["prev_hash"] == prev and
                r["hash"] == _digest(prev, r["seq"], r["created"], r["author_kind"], r["author_name"], r["body"],
                                     r["event"], task_no))
        if not good:
            return {"intact": False, "count": n, "head": (r["hash"] or "")[:12], "broken_at": n}
        prev = r["hash"]
    return {"intact": True, "count": n, "head": prev[:12] if n else "", "broken_at": None}


def entry_dict(r):
    t = r["task"]
    return {"id": r.get_id(), "seq": r["seq"], "kind": r["kind"], "author_kind": r["author_kind"],
            "author_name": r["author_name"] or "", "body": r["body"] or "", "event": r["event"],
            "task_id": t.get_id() if t is not None else None, "task_number": t["number"] if t is not None else None,
            "created": C.iso(r["created"]), "hash": (r["hash"] or "")[:12]}


def last_seq(tenancy):
    for r in app_tables.messages.search(tables.order_by("seq", ascending=False), tenancy=tenancy):
        return r["seq"]
    return 0


def unread_for(tenancy, side):
    """Messages from the other side newer than what `side` (landlord | tenant) last saw."""
    seen = tenancy["landlord_seen" if side == "landlord" else "tenant_seen"] or 0
    other = "tenant" if side == "landlord" else "landlord"
    return len([r for r in app_tables.messages.search(tenancy=tenancy, author_kind=other) if r["seq"] > seen])
