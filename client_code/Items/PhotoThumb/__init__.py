from anvil import *

from ._anvil_designer import PhotoThumbTemplate


class PhotoThumb(PhotoThumbTemplate):
    """One photo square. In the record (TaskView, ThreadEntry) it links to the full photo in a new tab; in the picker
    (Components/PhotoPicker) it is a preview with a remove button that raises x-remove (index=...).
    item = {src, alt, href?, index?, removable?}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        d = self.dom_nodes
        d["img"].src = p.get("src") or ""
        d["img"].alt = p.get("alt") or "Photo"
        if p.get("href"):
            d["link"].href = p["href"]
            d["link"].setAttribute("aria-label", (p.get("alt") or "Photo") + " (opens full size in a new tab)")
        else:
            d["link"].removeAttribute("href")
        d["rm"].hidden = not p.get("removable")
        d["rm"].setAttribute("aria-label", "Remove photo %d" % ((p.get("index") or 0) + 1))
        d["rm"].setAttribute("data-key", "rm-%d" % (p.get("index") or 0))

    def rm_click(self, event):
        if self.parent:
            self.parent.raise_event("x-remove", index=self.item.get("index") or 0)
