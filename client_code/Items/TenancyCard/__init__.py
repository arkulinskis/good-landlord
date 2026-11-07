from anvil import *

from ._anvil_designer import TenancyCardTemplate
from ... import gl, router, state


class TenancyCard(TenancyCardTemplate):
    """Tenants: one tenancy (unread, the last message, open requests, the tenant's last visit, open record, copy link).
    item = a tenancy dict."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t = self.item
        d = self.dom_nodes
        d["card"].classList.toggle("ended", t["status"] == "ended")
        d["initials"].textContent = state.initials(t["tenant_name"])
        d["name"].textContent = t["tenant_name"]
        d["rent"].textContent = (t["unit"] + " · " if t.get("unit") else "") + gl.money(t["rent"]) + "/month"
        d["unread"].textContent = "%d new" % t.get("unread", 0)
        d["unread"].hidden = not t.get("unread")
        d["ended"].hidden = t["status"] != "ended"
        lm = t.get("last_message")
        if lm:
            d["last_who"].textContent = ("You" if lm["author_kind"] == "landlord" else lm["author_name"]) + ":"
            d["last_body"].textContent = lm["body"]
            d["last_when"].textContent = "· " + gl.ago(lm["created"])
        else:
            d["last_who"].textContent = ""
            d["last_body"].textContent = "No messages yet." + ("" if t.get("tenant_last_visit") else " Send them their link!")
            d["last_when"].textContent = ""
        n = t.get("open_tasks") or 0
        d["open"].textContent = state.plural(n, "open request") if n else "No open requests"
        d["open"].className = "ui-badge " + ("warn" if n else "good")
        d["entries"].textContent = state.plural(t.get("entries") or 0, "entry", "entries")
        d["visit"].textContent = ("· tenant visited " + gl.ago(t["tenant_last_visit"])) if t.get("tenant_last_visit") else "· link not opened yet"
        d["record"].setAttribute("href", router.href("tenancy", t["id"]))

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        gl.copy(gl.tenant_link(self.item["token"]))
