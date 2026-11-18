import json

from anvil import *
from anvil.js import window

from ._anvil_designer import PhotoPickerTemplate
from ... import state

MAX = 6


def _plain(js_obj):
    """A JavaScript reply as a Python dict."""
    try:
        return json.loads(str(window.JSON.stringify(js_obj))) or {}
    except Exception:
        return {}


class PhotoPicker(PhotoPickerTemplate):
    """Photos for a repair request: Add photos opens the phone's camera roll / file picker (gl-photos.js shrinks each
    one to 2000 px JPEG, which also drops its GPS location), previews with remove buttons, then upload() sends them
    straight to the private Cloudflare bucket with links the server signed. Raises "change"."""

    def __init__(self, **properties):
        self._photos = []
        self._uploaded = None  # photo ids of the last upload, reused if sending fails for another reason
        super().__init__(**properties)
        self.thumbs.add_event_handler("x-remove", self._remove)
        self.dom_nodes["status"].setAttribute("role", "status")
        self._draw()

    @property
    def count(self):
        return len(self._photos)

    def _draw(self):
        n = len(self._photos)
        self.thumbs.items = [{"src": p["preview"], "alt": "Photo %d to add" % (i + 1), "index": i, "removable": True}
                             for i, p in enumerate(self._photos)]
        self.thumbs.visible = n > 0
        self.add_button.text = "Add more photos" if n else "Add photos"
        self.add_button.visible = n < MAX
        self.dom_nodes["hint"].textContent = ("%d of %d photos" % (n, MAX)) if n else \
            "Up to %d. Location data is removed before upload." % MAX

    def _say(self, text):
        self.dom_nodes["status"].textContent = text or ""

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self.add_button.enabled = False
        self._say("")
        try:
            got = window.GLPhotos.pick(MAX - len(self._photos))
            for p in got.photos:
                self._photos.append({"blob": p.blob, "preview": str(p.preview), "type": str(p.type),
                                     "size": int(p.size), "width": int(p.width), "height": int(p.height)})
            skipped = int(got.skipped or 0)
        finally:
            self.add_button.enabled = True
        if skipped:
            self._say("%s couldn't be opened as a photo. Try a JPEG or PNG." %
                      ("One file" if skipped == 1 else "%d files" % skipped))
        self._uploaded = None
        self._draw()
        self.raise_event("change")
        if self.add_button.visible:
            state.focus(self.add_button)

    def _remove(self, index, **event_args):
        if 0 <= index < len(self._photos):
            window.GLPhotos.revoke(self._photos.pop(index)["preview"])
        self._uploaded = None
        self._draw()
        self.raise_event("change")
        if self._photos:
            state.refocus(self.thumbs, "rm-%d" % min(index, len(self._photos) - 1))
        else:
            state.focus(self.add_button)

    def clear(self):
        for p in self._photos:
            window.GLPhotos.revoke(p["preview"])
        self._photos, self._uploaded = [], None
        self._say("")
        self._draw()

    def upload(self, get_tickets):
        """get_tickets([{type, size, width, height}]) makes the server call (photo_tickets / tenant_photo_tickets).
        Returns (photo_ids, None) or (None, "what went wrong")."""
        if not self._photos:
            return [], None
        if self._uploaded:
            return self._uploaded, None
        meta = [{"type": p["type"], "size": p["size"], "width": p["width"], "height": p["height"]} for p in self._photos]
        r = get_tickets(meta)
        if not isinstance(r, dict) or not r.get("ok"):
            return None, (r or {}).get("error") if isinstance(r, dict) else "The photos couldn't be sent."
        ids = []
        n = len(self._photos)
        for i, (t, p) in enumerate(zip(r["tickets"], self._photos)):
            self._say("Uploading photo %d of %d…" % (i + 1, n))
            res = _plain(window.GLPhotos.put(t["put_url"], p["blob"]))
            if not res.get("ok"):
                self._say("")
                return None, res.get("error") or "A photo didn't upload. Please try again."
            ids.append(t["id"])
        self._say("")
        self._uploaded = ids
        return ids, None
