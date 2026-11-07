from anvil import *

from ._anvil_designer import ThreadEntryTemplate
from ... import gl


class ThreadEntry(ThreadEntryTemplate):
    """One entry of the sealed record: a message bubble (mine on the right) or an event line (task moves, rent, the
    opening), with its time, number and seal fingerprint, and a day heading when the day changes.
    item = an entry dict + {side: 'landlord' | 'tenant', new_day: '...' or ''}. An event about a task raises x-task."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        d = self.dom_nodes
        d["day"].hidden = not e.get("new_day")
        d["day"].textContent = e.get("new_day") or ""
        time = gl.fmt_time(e["created"])
        mine = e["author_kind"] == e["side"]
        if e["kind"] == "message":
            d["ev"].hidden = True
            d["msg"].className = "gl-msg " + ("mine" if mine else "theirs")
            d["bub"].textContent = e["body"]
            d["who"].textContent = ("You" if mine else e["author_name"]) + " · " + time
            d["seal"].textContent = "#%d · %s" % (e["seq"], e["hash"][:6])
            d["seal"].setAttribute("title", "Entry #%d, sealed with fingerprint %s" % (e["seq"], e["hash"]))
        else:
            d["msg"].hidden = True
            lines = e["body"].split("\n")
            d["icon"].className = "ic ic-" + gl.EV_ICON.get(e.get("event") or "", "info")
            d["ev_who"].textContent = "" if e["author_kind"] == "system" else ("You" if mine else e["author_name"]) + " "
            d["ev_line"].textContent = lines[0]
            more = "\n".join(lines[1:])
            d["ev_more"].textContent = more
            d["ev_br"].hidden = not more
            d["ev_more"].hidden = not more
            d["ev_meta"].textContent = "%s · #%d · %s" % (time, e["seq"], e["hash"][:6])
            if e.get("task_id"):
                d["ev"].classList.add("has-task")
                d["ev"].setAttribute("role", "button")
                d["ev"].setAttribute("tabindex", "0")

    def ev_click(self, event):
        if self.item.get("task_id") and self.parent:
            self.parent.raise_event("x-task-id", task_id=self.item["task_id"])
