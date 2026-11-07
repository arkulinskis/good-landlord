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
admin = person("arkulinskis@gmail.com", "The Admin")
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
PUBLIC = {"get_me", "submit_feedback", "legal_state", "legal_accept",
          "tenant_view", "tenant_post", "tenant_request", "tenant_confirm"}  # the tenant side: the private link is the key
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
