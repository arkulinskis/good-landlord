import anvil.js
from anvil import *

from ._anvil_designer import LandingTemplate
from ... import state

# The app's video on the Addanapp YouTube channel (APP_MAKER/youtube/manifest.json), shown in the Watch section.
YT_VIDEO = "qv8jRRY0KG0"


class Landing(LandingTemplate):
    """#landing (Persuade): the before/after hero (drag between the shoebox of receipts and texts and the same rental in
    Good Landlord; a range input, so keys work too), the Watch section, both sides of the door, how it works, features,
    questions. Members see "Open the app" instead of the sign-up buttons."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = state.me()
        self.guest_cta.visible = not me
        self.member_cta.visible = bool(me)
        band = self.dom_nodes["band_cta"]
        band.setAttribute("href", "#home" if me else "#auth/signup")
        band.textContent = "Open the app" if me else "Start free"
        self.dom_nodes["ba_range"].addEventListener("input", anvil.js.report_exceptions(self._drag))
        self.dom_nodes["yt_cover"].addEventListener("click", anvil.js.report_exceptions(self._play))

    def _drag(self, event):
        self.dom_nodes["ba"].style.setProperty("--x", str(self.dom_nodes["ba_range"].value) + "%")

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="Good Landlord video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')
