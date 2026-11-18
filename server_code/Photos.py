"""Photos on repair requests, stored privately on Cloudflare R2 (tools/cloudflare/worker.js).

How a photo gets into the record:
  1. The browser shrinks each photo (gl-photos.js, longest side 2000 px, JPEG) and asks for upload links
     (photo_tickets / tenant_photo_tickets): one "pending" row per photo + a PUT link signed for 15 minutes.
  2. It uploads straight to the Worker (no bytes through Anvil). The Worker refuses to overwrite and stores the file's
     SHA-256.
  3. The request (tenant_request / landlord_new_task) or "Add photos" on a request (add_task_photos /
     tenant_add_photos) sends the row ids. claim() asks the Worker for each file's size, type and SHA-256, and
     Record.append seals those SHA-256s into the entry's fingerprint and marks the rows "attached". From then on the
     photo is part of the permanent record: nothing edits or deletes it, and removing or swapping one breaks the seal.

Nothing in the bucket is public: the photos are inside people's homes. Every view link is signed here, only for the
landlord and the tenant of that tenancy, and expires within two hours (bucketed by the hour so the browser can cache).
Photos are off in demo and sample tenancies (the public demo is open to everyone) and when the App Secret
"cloudflare_photos" (https://<signing key>@goodlandlord-photos.<subdomain>.workers.dev) isn't set.
"""
import hashlib
import hmac
import re
import secrets
import time
import urllib.parse

import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

from . import common as C
from . import Record

SECRET = "cloudflare_photos"
TYPES = ["image/jpeg", "image/png", "image/webp"]
MAX_BYTES = 4 * 1024 * 1024        # after the browser shrinks it, a photo is usually 300-900 KB
MAX_PER_SEND = 6
PER_TENANCY_DAY = 60
TICKET_TTL = 15 * 60
OFF = "Photos aren't switched on in this app yet."
DEMO_OFF = "Photos are off in the sample records. Add a real tenancy to attach photos."
_cache: dict = {"at": 0.0, "cf": None}


# ------------------------------------------------------------------------------------------------ storage
def config():
    """{"base": "https://goodlandlord-photos.x.workers.dev", "key": signing key} or None (cached for a minute)."""
    if time.time() - _cache["at"] < 60:
        return _cache["cf"]
    value = ""
    try:
        import anvil.secrets
        value = str(anvil.secrets.get_secret(SECRET) or "").strip()
    except Exception:
        value = ""
    m = re.match(r"^(https://)([0-9a-f]{32,128})@([\w.-]+)/?$", value)
    _cache.update(at=time.time(), cf={"base": m.group(1) + m.group(3), "key": m.group(2)} if m else None)
    return _cache["cf"]


def enabled():
    return config() is not None


def allowed(tenancy):
    """Can photos be added to this tenancy's record?"""
    return enabled() and tenancy is not None and not tenancy["is_demo"]


def link(cf, method, key, exp, max_=None):
    """A signed Worker address. method: GET | META | PUT | DELETE (the Worker checks the same HMAC)."""
    extra = str(max_) if method == "PUT" else ""
    sig = hmac.new(cf["key"].encode(), "\n".join([method, key, str(exp), extra]).encode(), hashlib.sha256).hexdigest()
    q = {"exp": exp, "sig": sig}
    if method == "PUT":
        q["max"] = max_
    if method == "META":
        q["meta"] = 1
    return "%s/%s?%s" % (cf["base"], key, urllib.parse.urlencode(q))


def view_url(cf, key):
    """Valid for one to two hours; the same address all hour, so the browser's cache works and polling doesn't reload."""
    return link(cf, "GET", key, (int(time.time()) // 3600 + 2) * 3600)


def _meta(cf, key):
    import anvil.http
    try:
        m = anvil.http.request(link(cf, "META", key, int(time.time()) + 300), json=True)
    except Exception:
        return None
    return m if isinstance(m, dict) and m.get("ok") else None


def _remove(cf, row):
    """Delete an unattached upload (row + file). Attached photos are never removed."""
    if row["status"] == "attached":
        return
    if cf and row["key"]:
        import anvil.http
        try:
            anvil.http.request(link(cf, "DELETE", row["key"], int(time.time()) + 300), method="DELETE", json=True)
        except Exception as e:
            print("photo delete failed:", row["key"], e)
    row.delete()


def drop_pending(tenancy, older_than=None):
    """Clean up uploads nobody attached (a closed dialog). older_than: seconds, None = all of them."""
    cf = config()
    for r in app_tables.photos.search(tenancy=tenancy, status="pending"):
        if older_than is None or (C.now() - r["created"]).total_seconds() > older_than:
            _remove(cf, r)


# ------------------------------------------------------------------------------------------------ views
def view(r, cf=None):
    cf = cf or config()
    return {"id": r.get_id(), "url": view_url(cf, r["key"]) if cf else "", "width": r["width"], "height": r["height"],
            "sha": r["sha256"] or "", "by": r["author_kind"], "name": r["author_name"] or "",
            "created": C.iso(r["created"])}


def maps(tenancy=None, owner=None):
    """({task_id: [photo]}, {message_id: [photo]}) for every attached photo of a tenancy (or an owner), oldest first."""
    q = {"status": "attached"}
    if tenancy is not None:
        q["tenancy"] = tenancy
    if owner is not None:
        q["owner"] = owner
    by_task, by_msg = {}, {}
    rows = list(app_tables.photos.search(tables.order_by("created"), **q))
    if not rows:
        return by_task, by_msg
    cf = config()
    for r in rows:
        v = view(r, cf)
        if r["task"] is not None:
            by_task.setdefault(r["task"].get_id(), []).append(v)
        if r["message"] is not None:
            by_msg.setdefault(r["message"].get_id(), []).append(v)
    return by_task, by_msg


def task_photos(task):
    cf = config()
    return [view(r, cf) for r in app_tables.photos.search(tables.order_by("created"), task=task, status="attached")]


# ------------------------------------------------------------------------------------------------ upload steps
def tickets(tenancy, author_kind, author_name, items):
    """Pending rows + signed upload links for up to MAX_PER_SEND photos. items: [{type, size, width, height}]."""
    cf = config()
    if cf is None:
        return C.fail(OFF)
    if tenancy["is_demo"]:
        return C.fail(DEMO_OFF)
    if not isinstance(items, list) or not items:
        return C.fail("Choose a photo first.")
    if len(items) > MAX_PER_SEND:
        return C.fail("Up to %d photos at a time." % MAX_PER_SEND)
    clean: list[dict] = []
    for it in items:
        it = it if isinstance(it, dict) else {}
        kind = str(it.get("type") or "").lower()
        size = C.num(it.get("size"), 0, 1e9, 0)
        if kind not in TYPES:
            return C.fail("Only photos (JPEG, PNG or WebP) can be added.")
        if not size or size > MAX_BYTES:
            return C.fail("One of the photos is too big, even after shrinking it. Try a smaller one.")
        clean.append({"type": kind, "width": int(C.num(it.get("width"), 0, 20000, 0)),
                      "height": int(C.num(it.get("height"), 0, 20000, 0))})
    drop_pending(tenancy, older_than=86400)
    day_ago = C.now().timestamp() - 86400
    recent = len([r for r in app_tables.photos.search(tenancy=tenancy) if r["created"].timestamp() > day_ago])
    if recent + len(clean) > PER_TENANCY_DAY:
        return C.fail("That's a lot of photos for one day. Please try again tomorrow.")
    exp = int(time.time()) + TICKET_TTL
    folder = re.sub(r"[^0-9a-z]", "", tenancy.get_id().lower())[:40] or "t"
    out = []
    for it in clean:
        key = "gl/%s/%s" % (folder, secrets.token_hex(16))
        r = app_tables.photos.add_row(owner=tenancy["owner"], tenancy=tenancy, key=key, content_type=it["type"],
                                      width=it["width"], height=it["height"], author_kind=author_kind,
                                      author_name=author_name, status="pending", created=C.now(), is_demo=False)
        out.append({"id": r.get_id(), "put_url": link(cf, "PUT", key, exp, MAX_BYTES), "type": it["type"]})
    return C.ok(tickets=out)


def claim(tenancy, photo_ids):
    """The pending rows for these ids, each checked with the Worker (arrived, a photo, its SHA-256). (rows, error)"""
    if not photo_ids:
        return [], None
    cf = config()
    if cf is None:
        return None, OFF
    if tenancy["is_demo"]:
        return None, DEMO_OFF
    if not isinstance(photo_ids, list) or len(photo_ids) > MAX_PER_SEND or len(set(map(str, photo_ids))) != len(photo_ids):
        return None, "Up to %d photos at a time." % MAX_PER_SEND
    rows = []
    for pid in photo_ids:
        r = C.row_by_id(app_tables.photos, pid)
        if r is None or r["tenancy"] != tenancy or r["status"] != "pending":
            return None, "A photo didn't upload. Remove it and add it again."
        m = _meta(cf, r["key"])
        sha = str((m or {}).get("sha256") or "")
        if m is None or not re.match(r"^[0-9a-f]{64}$", sha) or m.get("type") not in TYPES or not m.get("size"):
            return None, "A photo didn't finish uploading. Remove it and add it again."
        r.update(sha256=sha, size=m["size"], content_type=m["type"])
        rows.append(r)
    return rows, None


def _photo_event(tenancy, task, author_kind, name, rows, note):
    note = C.text(note, 1000, multiline=True)
    n = len(rows)
    body = "Added %d photo%s to #%d %s.%s" % (n, "" if n == 1 else "s", task["number"], task["title"],
                                              ("\n" + note) if note else "")
    when = C.now().replace(microsecond=0)
    task["updated"] = when
    Record.append(tenancy, "event", author_kind, name, body, task=task, event="photos", is_demo=tenancy["is_demo"],
                  when=when, photos=rows)


# ------------------------------------------------------------------------------------------------ callables
@anvil.server.callable(require_user=True)
def photo_tickets(tenancy_id, items):
    me = C.require_user()
    t = C.row_by_id(app_tables.tenancies, tenancy_id)
    if t is None or t["owner"] != me:
        return C.fail("That tenancy isn't yours.")
    if C.rate_limited("photo_tickets", 60, 3600):
        return C.fail("That's a lot of photos in one hour. Please try again later.")
    return tickets(t, "landlord", C.name_of(me), items)


@anvil.server.callable
def tenant_photo_tickets(token, items, name=None):
    from . import TenantPortal
    t = TenantPortal._tenancy(token)
    if t is None:
        return C.fail(TenantPortal.BAD_LINK)
    if C.rate_limited("tenant_photo_tickets", 30, 3600):
        return C.fail("That's a lot of photos in one hour. Please try again a little later.")
    return tickets(t, "tenant", TenantPortal._name(t, name), items)


@anvil.server.callable(require_user=True)
def add_task_photos(task_id, photo_ids, note=None):
    """The landlord adds photos to a request (before/after, the invoice). Sealed into the record as an event."""
    me = C.require_user()
    from . import Tenancy
    k = C.row_by_id(app_tables.tasks, task_id)
    if k is None or k["owner"] != me:
        return C.fail("That task isn't yours.")
    if not photo_ids:
        return C.fail("Choose a photo first.")
    t = k["tenancy"]
    rows, err = claim(t, photo_ids)
    if err:
        return C.fail(err)
    _photo_event(t, k, "landlord", C.name_of(me), rows, note)
    return C.ok(task=Tenancy.task_dict(k))


@anvil.server.callable
def tenant_add_photos(token, task_id, photo_ids, name=None, note=None):
    from . import TenantPortal
    t = TenantPortal._tenancy(token)
    if t is None:
        return C.fail(TenantPortal.BAD_LINK)
    k = C.row_by_id(app_tables.tasks, task_id)
    if k is None or k["tenancy"] != t:
        return C.fail("That request isn't part of this tenancy.")
    if not photo_ids:
        return C.fail("Choose a photo first.")
    if C.rate_limited("tenant_add_photos", 20, 3600):
        return C.fail("Please try again a little later.")
    rows, err = claim(t, photo_ids)
    if err:
        return C.fail(err)
    _photo_event(t, k, "tenant", TenantPortal._name(t, name), rows, note)
    return C.ok(task=TenantPortal._task(k))
