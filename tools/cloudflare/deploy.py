"""Put Good Landlord's repair photos on Cloudflare: private R2 bucket "goodlandlord-photos" + its Worker.

    python -I tools/cloudflare/deploy.py            create the bucket if needed, set the signing key, deploy, test
    python -I tools/cloudflare/deploy.py --test     only test the live Worker

Before the first run: `npx wrangler login` done once on this PC (same Cloudflare account as PlanPlate's media Worker).

The signing key is made once and kept OUTSIDE the repo in ~/.goodlandlord/cloudflare_photos.txt, as the exact value of
the Anvil App Secret "cloudflare_photos" (https://<key>@goodlandlord-photos.<subdomain>.workers.dev). Paste that value
into the Anvil editor: App Secrets -> cloudflare_photos. Never commit it.
"""
import hashlib
import hmac
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SECRET_FILE = pathlib.Path.home() / ".goodlandlord" / "cloudflare_photos.txt"
BUCKET = "goodlandlord-photos"
WRANGLER = "wrangler@4"


def npx():
    exe = shutil.which("npx.cmd") or shutil.which("npx")
    if not exe:
        sys.exit("npx not found: install Node.js first.")
    return exe


def wrangler(*args, stdin=None, check=True):
    r = subprocess.run([npx(), "--yes", WRANGLER, *args], cwd=HERE, input=stdin, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode:
        sys.exit("wrangler %s failed:\n%s" % (" ".join(args), out))
    return out


def parse(value):
    m = re.match(r"^(https://)([0-9a-f]{32,128})@([\w.-]+)/?$", value.strip())
    return (m.group(1) + m.group(3), m.group(2)) if m else (None, None)


def link(base, key, method, obj, ttl=600, max_=None):
    exp = int(time.time()) + ttl
    extra = str(max_) if method == "PUT" else ""
    sig = hmac.new(key.encode(), "\n".join([method, obj, str(exp), extra]).encode(), hashlib.sha256).hexdigest()
    q = {"exp": exp, "sig": sig}
    if method == "PUT":
        q["max"] = max_
    if method == "META":
        q["meta"] = 1
    return "%s/%s?%s" % (base, obj, urllib.parse.urlencode(q))


def http(method, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=dict({"User-Agent": "goodlandlord-deploy"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test(base, key):
    obj = "gl/test/" + secrets.token_hex(12)
    body = bytes(range(256)) * 4
    st, out, _ = http("PUT", link(base, key, "PUT", obj, max_=5000), body, {"Content-Type": "image/jpeg"})
    assert st == 200, ("signed upload", st, out[:200])
    assert json.loads(out)["sha256"] == hashlib.sha256(body).hexdigest(), "the Worker seals the right SHA-256"
    st, _, _ = http("PUT", link(base, key, "PUT", obj, max_=5000), body, {"Content-Type": "image/jpeg"})
    assert st == 409, ("never overwrites a photo", st)
    other = "gl/test/" + secrets.token_hex(12)
    st, _, _ = http("PUT", link(base, key, "PUT", obj, max_=5000).replace(obj, other), body, {"Content-Type": "image/jpeg"})
    assert st == 403, ("an upload link only works for its own file", st)
    st, _, _ = http("PUT", link(base, key, "PUT", other, max_=100), body, {"Content-Type": "image/jpeg"})
    assert st == 413, ("size limit", st)
    st, _, _ = http("PUT", link(base, key, "PUT", other, max_=5000), body, {"Content-Type": "text/html"})
    assert st == 415, ("photos only", st)
    st, _, _ = http("GET", "%s/%s" % (base, obj))
    assert st == 403, ("private: no unsigned reads", st)
    st, out, h = http("GET", link(base, key, "GET", obj))
    assert st == 200 and out == body and h.get("Content-Type") == "image/jpeg", ("signed read", st, h)
    st, out, _ = http("GET", link(base, key, "META", obj))
    m = json.loads(out)
    assert st == 200 and m["size"] == len(body) and m["sha256"] == hashlib.sha256(body).hexdigest(), ("file info", st, out)
    st, _, _ = http("DELETE", link(base, key, "DELETE", obj))
    assert st == 200, ("delete", st)
    st, _, _ = http("GET", link(base, key, "GET", obj))
    assert st == 404, ("deleted file is gone", st)
    print("Live test OK: signed upload + SHA-256, no overwrite, wrong-file/size/type refusals, private reads, "
          "file info, delete (%s)" % base)


def main():
    args = sys.argv[1:]
    value = SECRET_FILE.read_text(encoding="utf-8").strip() if SECRET_FILE.exists() else ""
    if "--test" in args:
        base, key = parse(value)
        if not base:
            sys.exit("No signing key yet: run without --test first.")
        return test(base, key)

    out = wrangler("whoami", check=False)
    if "not authenticated" in out.lower():
        sys.exit("Not logged in to Cloudflare. Run once: npx wrangler login")
    if BUCKET not in wrangler("r2", "bucket", "list"):
        wrangler("r2", "bucket", "create", BUCKET)
        print("Created R2 bucket", BUCKET)
    base, key = parse(value)
    key = key or secrets.token_hex(32)
    out = wrangler("deploy")
    m = re.search(r"https://goodlandlord-photos\.[\w-]+\.workers\.dev", out)
    if not m:
        sys.exit("Deployed, but couldn't find the Worker's address in wrangler's output:\n" + out)
    base = m.group(0)
    wrangler("secret", "put", "SIGNING_KEY", stdin=key + "\n")
    value = "https://%s@%s" % (key, base[len("https://"):])
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_bytes((value + "\n").encode("utf-8"))
    print("Worker live at", base)
    print("Anvil App Secret 'cloudflare_photos' value saved in", SECRET_FILE)
    time.sleep(5)  # the new secret takes a moment to reach every Cloudflare location
    test(base, key)


if __name__ == "__main__":
    main()
