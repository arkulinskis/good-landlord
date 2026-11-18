"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python -I tools/testing/test_server.py          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
import anvil.secrets  # noqa: E402
anvil.secrets.SECRETS["admin_emails"] = "admin@example.com"  # the App Secret, faked
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("admin@example.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5 and ov["properties"] == 0
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

# ---------------------------------------------------------------------------------- demo data (public demo + the tenant link)
as_user(None)
assert denied("get_portfolio")
tv = ok(call("tenant_view", "demo-upstairs"))
assert M["DemoData"].state() == "loaded", "demo loads on first visit"
assert tv["landlord_name"] == "Maya Chen" and tv["seal"]["intact"] and tv["seal"]["count"] == len(tv["entries"]) > 5
assert len(tv["tasks"]) == 3 and all("cost" not in k for k in tv["tasks"]), "tenants never see repair costs"
assert tv["stats"]["requests"] >= 1 and tv["stats"]["reply_hours"] is not None
assert "maya.demo@example.com" not in json.dumps(tv), "no landlord email on the tenant side"
bad(call("tenant_view", "nope"))
bad(call("tenant_view", "x" * 30))
bad(call("tenant_view", None))

# ---------------------------------------------------------------------------------- landlord: properties, mortgages, prefs
as_user(ana)
pf = call("get_portfolio")
assert pf["properties"] == [] and pf["prefs"]["currency"] == "CAD" and len(pf["categories"]) > 10
bad(call("save_property", {"name": "x"}))
bad(call("save_property", "nonsense"))
bad(call("save_property", {"name": "Future", "purchase_date": "2999-01-01"}))
prop = ok(call("save_property", {"name": "Elm Street Triplex", "address": "9 Elm St", "kind": "triplex", "units": "3",
                                  "purchase_price": "600,000", "purchase_date": "2020-05-01", "down_payment": 120000,
                                  "closing_costs": 9000, "current_value": 700000, "appreciation": 3, "door": "honey"}))["property"]
assert prop["purchase_price"] == 600000 and prop["units"] == 3 and prop["door"] == "honey" and prop["selling_pct"] == 5
prop = ok(call("save_property", dict(prop, name="Elm Triplex")))["property"]
assert prop["name"] == "Elm Triplex"
ok(call("save_estimate", prop["id"], 720000, 4.5, 4))
assert T.properties.get_by_id(prop["id"])["current_value"] == 720000
bad(call("save_mortgage", {"property_id": prop["id"], "amount": 0, "rate": 4, "start_date": "2020-06-01"}))
bad(call("save_mortgage", {"property_id": prop["id"], "amount": 480000, "start_date": "2020-06-01"}))
bad(call("save_mortgage", {"property_id": "nope", "amount": 480000, "rate": 4, "start_date": "2020-06-01"}))
mort = ok(call("save_mortgage", {"property_id": prop["id"], "lender": "Bank", "amount": 480000, "rate": 4.1, "amort_years": 25,
                                 "term_years": 5, "start_date": "2020-06-01", "frequency": "biweekly", "compounding": "weird"}))["mortgage"]
assert mort["frequency"] == "biweekly" and mort["compounding"] == "semiannual"
ok(call("save_prefs", {"currency": "USD", "region": "us", "compounding": "monthly"}))
assert call("get_portfolio")["prefs"] == {"currency": "USD", "region": "us", "compounding": "monthly"}
ok(call("save_prefs", {"currency": "XXX"}))
assert call("get_portfolio")["prefs"]["currency"] == "USD"
ok(call("save_prefs", {"currency": "CAD"}))

# someone else can't touch Ana's things
as_user(bob)
assert call("get_portfolio")["properties"] == []
bad(call("save_property", dict(prop, name="Stolen")))
bad(call("save_estimate", prop["id"], 1))
bad(call("archive_property", prop["id"]))
bad(call("save_mortgage", dict(mort, rate=1)))
ok(call("delete_mortgage", mort["id"]))
ok(call("delete_property", prop["id"]))
assert T.properties.get_by_id(prop["id"]) is not None and T.mortgages.get_by_id(mort["id"]) is not None
bad(call("save_tenancy", {"property_id": prop["id"], "tenant_name": "Eve"}))
bad(call("add_entry", {"property_id": prop["id"], "category": "rent", "amount": 1}))

# ---------------------------------------------------------------------------------- tenancies and the record
as_user(ana)
bad(call("save_tenancy", {"property_id": prop["id"], "tenant_name": "x"}))
bad(call("save_tenancy", {"property_id": prop["id"], "tenant_name": "Rae", "tenant_email": "not-an-email"}))
bad(call("save_tenancy", {"property_id": prop["id"], "tenant_name": "Rae", "start_date": "2025-01-01", "end_date": "2024-01-01"}))
ten = ok(call("save_tenancy", {"property_id": prop["id"], "unit": "Unit 1", "tenant_name": "Rae Lindqvist",
                               "tenant_email": "rae@example.com", "rent": "1,600", "due_day": 40, "start_date": "2024-09-01"}))["tenancy"]
assert ten["due_day"] == 28 and ten["rent"] == 1600 and len(ten["token"]) > 20 and ten["entries"] == 1 and ten["unread"] == 0
tok = ten["token"]
ten2 = ok(call("save_tenancy", {"property_id": prop["id"], "unit": "Unit 2", "tenant_name": "Typo Person", "rent": 1}))["tenancy"]
ok(call("delete_tenancy", ten2["id"]))
assert T.tenancies.get_by_id(ten2["id"]) is None, "an unused record can be deleted"

as_user(None)
v = ok(call("tenant_view", tok))
assert v["tenancy"]["tenant_name"] == "Rae Lindqvist" and v["property"]["name"] == "Elm Triplex" and v["currency"] == "CAD"
assert "ana@example.com" not in json.dumps(v)
bad(call("tenant_post", tok, "Rae", "   "))
ok(call("tenant_post", tok, "Rae", "Hello! The heating is on, thanks."))
bad(call("tenant_request", tok, "Rae", "x"))
req = ok(call("tenant_request", tok, "", "Leaky shower head", "Drips all night", "plumbing", "urgent"))["task"]
assert req["number"] == 1 and req["status"] == "requested" and req["requested_by"] == "tenant" and req["requested_name"] == "Rae Lindqvist"
bad(call("tenant_confirm", tok, req["id"], True), "can't confirm before done")

as_user(ana)
pf = call("get_portfolio")
t0 = [t for t in pf["tenancies"] if t["id"] == ten["id"]][0]
assert t0["unread"] == 2 and t0["open_tasks"] == 1 and pf["tasks"][0]["title"] == "Leaky shower head"
g = ok(call("get_tenancy", ten["id"]))
assert g["seal"]["intact"] and g["seal"]["count"] == 3 and len(g["entries"]) == 3 and g["entries"][2]["task_number"] == 1
assert [t for t in call("get_portfolio")["tenancies"] if t["id"] == ten["id"]][0]["unread"] == 0, "opening the record marks it read"
bad(call("landlord_post", ten["id"], ""))
ok(call("landlord_post", ten["id"], "I'll send someone tomorrow."))
bad(call("set_task_status", req["id"], "nonsense"))
bad(call("set_task_status", req["id"], "scheduled"), "scheduling needs a date")
bad(call("set_task_status", req["id"], "declined", None, ""), "declining needs a reason")
k = ok(call("set_task_status", req["id"], "scheduled", "2026-11-04", "Plumber in the morning"))["task"]
assert k["status"] == "scheduled" and k["scheduled_for"] == "2026-11-04" and k["acknowledged_at"]
k = ok(call("set_task_status", req["id"], "in_progress"))["task"]
assert k["started_at"]
k = ok(call("set_task_status", req["id"], "done", None, "New shower head", "85.50"))["task"]
assert k["done_at"] and k["cost"] == 85.5
e = T.ledger.get(task=T.tasks.get_by_id(req["id"]))
assert e["category"] == "repairs" and e["amount"] == 85.5, "a finished repair's cost lands in the ledger"
own = ok(call("landlord_new_task", ten["id"], "Test smoke alarms", "", "safety", "normal"))["task"]
assert own["number"] == 2 and own["requested_by"] == "landlord" and own["acknowledged_at"]
bad(call("landlord_new_task", ten["id"], ""))
ok(call("save_tenancy", dict(ten, rent=1650)))

as_user(bob)
bad(call("get_tenancy", ten["id"]))
bad(call("landlord_post", ten["id"], "hi"))
bad(call("set_task_status", req["id"], "done"))
bad(call("reset_link", ten["id"]))
bad(call("end_tenancy", ten["id"]))
bad(call("verify_record", ten["id"]))
ok(call("delete_tenancy", ten["id"]))
assert T.tenancies.get_by_id(ten["id"]) is not None

as_user(None)
bad(call("tenant_confirm", tok, own["id"], True), "a request that isn't done")
k = ok(call("tenant_confirm", tok, req["id"], False, "Rae", "Still drips a little"))["task"]
assert k["status"] == "requested" and k["done_at"] is None
as_user(ana)
ok(call("set_task_status", req["id"], "done"))
as_user(None)
k = ok(call("tenant_confirm", tok, req["id"], True))["task"]
assert k["confirmed_at"]
bad(call("tenant_confirm", tok, T.tasks.search(is_demo=True)[0].get_id(), True), "other tenancies' tasks")
v = ok(call("tenant_view", tok))
assert v["seal"]["intact"] and any("Rent changed" in x["body"] for x in v["entries"])

# the record can't be quietly changed: editing or removing an entry breaks the seal
as_user(ana)
n = ok(call("verify_record", ten["id"]))["seal"]["count"]
row = T.messages.search(tenancy=T.tenancies.get_by_id(ten["id"]), seq=2)[0]
orig = row["body"]
row["body"] = "I never said that"
s2 = ok(call("verify_record", ten["id"]))["seal"]
assert not s2["intact"] and s2["broken_at"] == 2
row["body"] = orig
assert ok(call("verify_record", ten["id"]))["seal"]["intact"]
row3 = T.messages.search(tenancy=T.tenancies.get_by_id(ten["id"]), seq=3)[0]
saved = dict(row3)
row3.delete()
assert not ok(call("verify_record", ten["id"]))["seal"]["intact"], "a deleted entry breaks the chain"
T.messages.add_row(**saved)
assert ok(call("verify_record", ten["id"]))["seal"]["count"] == n
for name in ("delete_message", "edit_message", "delete_entry_record"):
    assert name not in anvil.server.CALLABLES, "no way to edit or delete record entries"

# link reset, ending, the used record stays
newtok = ok(call("reset_link", ten["id"]))["token"]
assert newtok != tok
as_user(None)
bad(call("tenant_view", tok), "the old link stops working")
ok(call("tenant_view", newtok))
as_user(ana)
bad(call("delete_tenancy", ten["id"]), "a used record is kept")
bad(call("delete_property", prop["id"]), "a property with records can only be archived")
ok(call("end_tenancy", ten["id"], "2026-10-31"))
assert T.tenancies.get_by_id(ten["id"])["status"] == "ended"
ok(call("reopen_tenancy", ten["id"]))
assert T.tenancies.get_by_id(ten["id"])["status"] == "active"
ok(call("archive_property", prop["id"], True))
assert call("get_portfolio")["properties"][0]["archived"] is True
ok(call("archive_property", prop["id"], False))

# ---------------------------------------------------------------------------------- ledger and the rent roll
bad(call("add_entry", {"property_id": prop["id"], "category": "nope", "amount": 10}))
bad(call("add_entry", {"property_id": prop["id"], "category": "repairs", "amount": -5}))
bad(call("add_entry", {"property_id": "nope", "category": "repairs", "amount": 5}))
ex = ok(call("add_entry", {"property_id": prop["id"], "category": "insurance", "amount": "1,200.00", "date": "2026-02-03", "memo": "Policy"}))["entry"]
assert ex["kind"] == "expense" and ex["amount"] == 1200 and ex["date"] == "2026-02-03"
ex = ok(call("update_entry", ex["id"], dict(ex, amount=1250)))["entry"]
assert ex["amount"] == 1250
bad(call("mark_rent_paid", ten["id"], "2026-13"))
rp = ok(call("mark_rent_paid", ten["id"], "2026-10"))["entry"]
assert rp["amount"] == 1650 and rp["rent_month"] == "2026-10" and rp["category"] == "rent"
bad(call("mark_rent_paid", ten["id"], "2026-10"), "a month can't be recorded twice")
g = ok(call("get_tenancy", ten["id"]))
assert g["rent_payments"][0]["month"] == "2026-10" and "Rent for October 2026 received" in g["entries"][-1]["body"]
ok(call("delete_entry", rp["id"]))
assert "Removed the rent record" in ok(call("get_tenancy", ten["id"]))["entries"][-1]["body"]
as_user(bob)
bad(call("update_entry", ex["id"], ex))
ok(call("delete_entry", ex["id"]))
assert T.ledger.get_by_id(ex["id"]) is not None
bad(call("mark_rent_paid", ten["id"], "2026-09"))

# ---------------------------------------------------------------------------------- repair photos (Cloudflare R2)
import hashlib as _hl  # noqa: E402
import urllib.parse as _up  # noqa: E402
import anvil.http  # noqa: E402

PH = M["Photos"]
CF_BASE = "https://goodlandlord-photos.test.workers.dev"
CF_KEY = "ab" * 32
FILES = {}  # key -> {size, type, sha256}: the fake bucket


def _fake_worker(url, method, data):
    u = _up.urlparse(url)
    key = u.path[1:]
    q = dict(_up.parse_qsl(u.query))
    meth = "META" if "meta" in q else method
    extra = q.get("max", "") if meth == "PUT" else ""
    want = PH.hmac.new(CF_KEY.encode(), "\n".join([meth, key, q.get("exp", ""), extra]).encode(), _hl.sha256).hexdigest()
    if q.get("sig") != want:
        return anvil.http.HttpError(403, "bad signature")
    if meth == "META":
        return dict(FILES[key], ok=True) if key in FILES else anvil.http.HttpError(404, "")
    if meth == "DELETE":
        FILES.pop(key, None)
        return {"ok": True}
    return anvil.http.HttpError(405, "")


def upload(ticket, body=b"photo"):
    """What the browser does with a ticket: PUT the bytes (here: drop them in the fake bucket)."""
    key = _up.urlparse(ticket["put_url"]).path[1:]
    FILES[key] = {"size": len(body), "type": ticket["type"], "sha256": _hl.sha256(body).hexdigest()}
    return key


JPG = {"type": "image/jpeg", "size": 250000, "width": 2000, "height": 1500}
anvil.http.REPLIES[CF_BASE] = _fake_worker
PH._cache["at"] = 0
anvil.secrets.SECRETS.pop("cloudflare_photos", None)
as_user(ana)
assert not ok(call("get_tenancy", ten["id"]))["photos_on"], "no secret: photos are off"
bad(call("photo_tickets", ten["id"], [JPG]), "no secret: no uploads")
anvil.secrets.SECRETS["cloudflare_photos"] = "https://%s@%s" % (CF_KEY, CF_BASE[len("https://"):])
PH._cache["at"] = 0
assert ok(call("get_tenancy", ten["id"]))["photos_on"]

# the tenant asks for a repair with two photos
as_user(None)
tok_now = T.tenancies.get_by_id(ten["id"])["token"]
bad(call("tenant_photo_tickets", "nope-nope-nope", [JPG]), "a bad link gets no upload links")
bad(call("tenant_photo_tickets", tok_now, []), "nothing chosen")
bad(call("tenant_photo_tickets", tok_now, [dict(JPG, type="text/html")]), "photos only")
bad(call("tenant_photo_tickets", tok_now, [dict(JPG, size=50 * 1024 * 1024)]), "too big")
bad(call("tenant_photo_tickets", tok_now, [JPG] * 7), "six at a time")
tk = ok(call("tenant_photo_tickets", tok_now, [JPG, JPG], "Rae"))["tickets"]
assert len(tk) == 2 and all(t["put_url"].startswith(CF_BASE + "/gl/") for t in tk)
assert all(T.photos.get_by_id(t["id"])["status"] == "pending" for t in tk)
bad(call("tenant_request", tok_now, "Rae", "Mould in the bathroom", "", "other", "normal", [t["id"] for t in tk]),
    "photos that never arrived are refused")
assert not T.tasks.search(title="Mould in the bathroom"), "nothing is created when a photo is missing"
k1, k2 = upload(tk[0], b"one"), upload(tk[1], b"two")
r = ok(call("tenant_request", tok_now, "Rae", "Mould in the bathroom", "Behind the bath", "other", "normal",
            [t["id"] for t in tk]))["task"]
assert len(r["photos"]) == 2 and r["photos"][0]["url"].startswith(CF_BASE + "/" + k1 + "?") and r["can_photo"]
assert "cost" not in r, "tenants still don't see costs"
assert {p["sha"] for p in r["photos"]} == {_hl.sha256(b"one").hexdigest(), _hl.sha256(b"two").hexdigest()}
bad(call("tenant_request", tok_now, "Rae", "Again", "", "other", "normal", [tk[0]["id"]]), "a photo is attached once")
tv = ok(call("tenant_view", tok_now))
assert tv["photos_on"] and tv["seal"]["intact"]
ev = [e for e in tv["entries"] if e["event"] == "requested" and e["task_id"] == r["id"]][0]
assert len(ev["photos"]) == 2, "the request's entry carries its photos"
assert [t for t in tv["tasks"] if t["id"] == r["id"]][0]["photos"]

# the landlord sees them, adds an "after" photo; someone else can't
as_user(ana)
g = ok(call("get_tenancy", ten["id"]))
assert len([t for t in g["tasks"] if t["id"] == r["id"]][0]["photos"]) == 2
assert len([t for t in call("get_portfolio")["tasks"] if t["id"] == r["id"]][0]["photos"]) == 2
lt = ok(call("photo_tickets", ten["id"], [JPG]))["tickets"]
upload(lt[0], b"after")
bad(call("add_task_photos", r["id"], []), "nothing chosen")
r2 = ok(call("add_task_photos", r["id"], [lt[0]["id"]], "All cleaned and sealed."))["task"]
assert len(r2["photos"]) == 3 and r2["photos"][-1]["by"] == "landlord"
last = T.messages.search(tenancy=T.tenancies.get_by_id(ten["id"]), event="photos")[0]
assert last["body"].startswith("Added 1 photo to #") and "All cleaned" in last["body"]
own_task = ok(call("landlord_new_task", ten["id"], "Paint the hall", "", "other", "normal", []))["task"]
assert own_task["photos"] == []
as_user(bob)
bad(call("photo_tickets", ten["id"], [JPG]), "not bob's tenancy")
bad(call("add_task_photos", r["id"], [lt[0]["id"]]), "not bob's task")
as_user(None)
tk3 = ok(call("tenant_photo_tickets", tok_now, [JPG]))["tickets"]
upload(tk3[0], b"three")
bad(call("tenant_add_photos", tok_now, "not-a-task", [tk3[0]["id"]]))
ok(call("tenant_add_photos", tok_now, r["id"], [tk3[0]["id"]], "Rae", "Still a little damp."))
as_user(ana)
assert ok(call("verify_record", ten["id"]))["seal"]["intact"], "photos keep the seal intact"

# the seal covers the photos: swap a fingerprint or drop a photo and it breaks
prow = T.photos.get_by_id(tk[0]["id"])
real = prow["sha256"]
prow["sha256"] = "0" * 64
assert not ok(call("verify_record", ten["id"]))["seal"]["intact"], "a swapped photo breaks the seal"
prow["sha256"] = real
prow["status"] = "removed"
assert not ok(call("verify_record", ten["id"]))["seal"]["intact"], "a removed photo breaks the seal"
prow["status"] = "attached"
assert ok(call("verify_record", ten["id"]))["seal"]["intact"]
for name in ("delete_photo", "remove_photo"):
    assert name not in anvil.server.CALLABLES, "no way to delete an attached photo"

# a photo can't be claimed by another tenancy; demo/sample records have photos off
other = ok(call("save_tenancy", {"property_id": prop["id"], "unit": "Unit 2", "tenant_name": "Sam Other", "rent": 900,
                                 "due_day": 1, "start_date": "2026-01-01"}))["tenancy"]
ot = ok(call("photo_tickets", ten["id"], [JPG]))["tickets"]
upload(ot[0], b"x")
bad(call("landlord_new_task", other["id"], "Steal", "", "other", "normal", [ot[0]["id"]]), "photos stay in their tenancy")
as_user(None)
bad(call("tenant_photo_tickets", "demo-upstairs", [JPG]), "the public demo takes no photos")
assert ok(call("tenant_view", "demo-upstairs"))["photos_on"] is False

# unattached uploads are cleaned up: deleting an unused tenancy removes them, files too
as_user(ana)
pend = ok(call("photo_tickets", other["id"], [JPG]))["tickets"]
pk = upload(pend[0], b"never used")
ok(call("delete_tenancy", other["id"]))
assert T.photos.get_by_id(pend[0]["id"]) is None and pk not in FILES, "a deleted tenancy leaves no stray photos"

# ---------------------------------------------------------------------------------- the sample portfolio
as_user(ana)
ok(call("load_sample"))
bad(call("load_sample"), "only once")
pf = call("get_portfolio")
assert pf["has_sample"] and len(pf["properties"]) == 4 and len(pf["tenancies"]) == 5 and len(pf["ledger"]) > 100
sample_t = [t for t in pf["tenancies"] if t["demo"]]
assert all(t["token"] not in M["DemoData"].PUBLIC_TOKENS for t in sample_t), "the sample gets its own private links"
assert any(t["unread"] for t in sample_t) and any(k["status"] == "requested" for k in pf["tasks"])
st = ok(call("get_tenancy", sample_t[0]["id"]))
assert st["seal"]["intact"]
ok(call("clear_sample"))
pf = call("get_portfolio")
assert not pf["has_sample"] and len(pf["properties"]) == 1 and len(pf["tenancies"]) == 1, "clearing the sample keeps real data"
assert ok(call("verify_record", ten["id"]))["seal"]["intact"]
assert T.tenancies.get(token="demo-upstairs") is not None, "the public demo stays"

# ---------------------------------------------------------------------------------- admin demo controls
as_user(admin)
ok(call("demo_remove"))
assert M["DemoData"].state() == "removed" and not T.users.search(is_demo=True) and not T.messages.search(is_demo=True)
assert len(T.messages.search()) > 5, "removing demo data keeps real records"
as_user(None)
bad(call("tenant_view", "demo-upstairs"))
assert M["DemoData"].state() == "removed", "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert len(T.tenancies.search(token="demo-upstairs")) == 1, "reloading replaces the demo instead of doubling it"
ov = call("admin_overview")
assert ov["properties"] == 1 and ov["tenancies"] == 1 and ov["landlords"] == 1

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"log_client_error", "session_ping", "get_me", "submit_feedback", "legal_state", "legal_accept",
          "tenant_view", "tenant_post", "tenant_request", "tenant_confirm",
          "tenant_photo_tickets", "tenant_add_photos"}  # the tenant side: the private link is the key
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
