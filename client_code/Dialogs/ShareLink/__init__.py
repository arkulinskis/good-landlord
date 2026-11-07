from anvil import *
from anvil.js import window

from ._anvil_designer import ShareLinkTemplate
from ... import gl, state


class ShareLink(ShareLinkTemplate):
    """The tenant's private link: copy it, copy a ready message, email it, or make a new link (reset_link: the old
    one stops working at once). Closes with "reset" after a new link, else None."""

    def __init__(self, tenancy=None, property_name="", **properties):
        super().__init__(**properties)
        t: dict = dict(tenancy or {})
        self._t = t
        link = gl.tenant_link(t["token"])
        first = gl.first_name(t["tenant_name"])
        self.title_label.text = first + "'s private link"
        state.heading(self.title_label, 2)
        self._text = ("Hi " + first + ", here is your private page for " + property_name + (" (" + t["unit"] + ")" if t.get("unit") else "") +
                      ": " + link + "\nWrite to me or ask for repairs there. Everything is kept for both of us and nobody can delete it.")
        self._link = link
        self.link_box.text = link
        self.msg_box.text = self._text
        state.set_control_attr(self.link_box, "readonly", "readonly")
        state.set_control_attr(self.link_box, "aria-label", "The tenant's private link")
        state.set_control_attr(self.msg_box, "readonly", "readonly")
        email = t.get("tenant_email")
        self.mail_link.visible = bool(email)
        if email:
            self.dom_nodes["mail"].setAttribute("href", "mailto:" + email + "?subject=" + window.encodeURIComponent("Your page for " + property_name) +
                                                "&body=" + window.encodeURIComponent(self._text))

    @handle("copy_link", "click")
    def copy_link_click(self, **event_args):
        getattr(state.control(self.link_box), "select")()
        gl.copy(self._link)

    @handle("copy_msg", "click")
    def copy_msg_click(self, **event_args):
        getattr(state.control(self.msg_box), "select")()
        gl.copy(self._text)

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        if confirm("The old link stops working right away. You'll need to send the new one to your tenant.", title="Make a new link?",
                   buttons=[("Cancel", False), ("New link", True)], role="app-dialog"):
            if state.call("reset_link", self._t["id"]):
                state.toast("New link made", "ok")
                self.raise_event("x-close-alert", value="reset")

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
