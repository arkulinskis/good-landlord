from anvil import *

from ._anvil_designer import ProfileTemplate
from ... import auth, gl, router, state


class Profile(ProfileTemplate):
    """#profile: your name, light/dark, a password reset link, money and taxes (currency, country, usual mortgage
    compounding: save_prefs), Privacy & Terms, feedback, sign out."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self._show_me()
        self._show_theme()
        prefs = gl.load()["prefs"]
        self.currency_box.items = [(label, key) for key, label in gl.CURRENCIES]
        self.currency_box.selected_value = prefs.get("currency") or "CAD"
        self.region_box.items = [(label, key) for key, label in gl.REGIONS]
        self.region_box.selected_value = prefs.get("region") or "ca"
        self.comp_box.items = [("Twice a year (Canadian fixed rate)", "semiannual"), ("Monthly (US, variable)", "monthly")]
        self.comp_box.selected_value = prefs.get("compounding") or "semiannual"

    @handle("prefs_button", "click")
    def prefs_button_click(self, **event_args):
        r = state.call("save_prefs", {"currency": self.currency_box.selected_value, "region": self.region_box.selected_value,
                                      "compounding": self.comp_box.selected_value})
        if r:
            state.toast("Saved", "ok")
            gl.load(quiet=True)

    def _show_me(self):
        me = state.me()
        self.initials.text = state.initials(me.get("name"))
        self.name_title.text = me.get("name") or ""
        joined = state.month_year(me.get("joined"))
        self.email_line.text = (me.get("email") or "") + (" · member since " + joined if joined else "")
        self.name_box.text = me.get("name") or ""
        self.admin_link.visible = bool(me.get("is_admin"))

    def _show_theme(self):
        t = state.theme()
        for name, el in (("auto", self.theme_auto), ("light", self.theme_light), ("dark", self.theme_dark)):
            el.classes["on"] = name == t

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-pick"))
        self._show_theme()

    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.save_button_click()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        name = (self.name_box.text or "").strip()
        if len(name) < 2:
            state.toast("Please tell us your name.", "error")
            return
        r = state.call("update_profile", name)
        if r:
            state.set_me(r["me"])
            self._show_me()
            state.toast("Saved", "ok")

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        r = auth.reset(state.me()["email"])
        state.toast(r["message"], "ok")

    def feedback_click(self, event):
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        state.toast("Signed out. See you soon!")
        router.go("landing")
