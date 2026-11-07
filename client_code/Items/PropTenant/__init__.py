from anvil import *

from ._anvil_designer import PropTenantTemplate
from ... import gl, router, state


class PropTenant(PropTenantTemplate):
    """Property page: one tenancy (rent, due day, open requests) with Copy link and Record. item = a tenancy dict."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t = self.item
        d = self.dom_nodes
        d["name"].textContent = t["tenant_name"]
        d["unread"].textContent = "%d new" % (t.get("unread") or 0)
        d["unread"].hidden = not t.get("unread")
        d["ended"].hidden = t["status"] != "ended"
        d["sub"].textContent = ((t["unit"] + " · ") if t.get("unit") else "") + gl.money(t["rent"]) + " a month, due on day %d" % t["due_day"] + \
            (" · " + state.plural(t["open_tasks"], "open request") if t.get("open_tasks") else "")
        d["record"].setAttribute("href", router.href("tenancy", t["id"]))

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        gl.copy(gl.tenant_link(self.item["token"]))
