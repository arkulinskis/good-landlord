from anvil import *

from ._anvil_designer import ReportRowTemplate
from ... import gl


def status_of(rep, side):
    """(chip text, chip class) of a condition report seen from `side` (landlord | tenant)."""
    a = rep.get("answer")
    if a:
        return ("Agreed", "done") if a["agree"] else ("Disputed", "requested")
    if rep["author_kind"] == side:
        return "Waiting for an answer", "acknowledged"
    return "Please check it", "in_progress"


class ReportRow(ReportRowTemplate):
    """A condition report in a list (Tenancy and tenant page). item = a report dict from Agreements.summary + {side}.
    A click raises x-report (report=...) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        d = self.dom_nodes
        text, cls = status_of(r, r.get("side") or "landlord")
        d["chip"].className = "gl-status gl-st-" + cls
        d["chip"].textContent = text
        d["num"].textContent = "#%d" % r["seq"]
        d["title"].textContent = r["label"] + " condition report"
        mine = r["author_kind"] == (r.get("side") or "landlord")
        rooms = len(r.get("rooms") or [])
        bits = [("By you" if mine else "By " + r["author_name"]) + " · " + gl.fmt_date(r["created"]),
                "%d room%s" % (rooms, "" if rooms == 1 else "s")]
        if r.get("changes"):
            bits.append("%d change%s since move-in" % (len(r["changes"]), "" if len(r["changes"]) == 1 else "s"))
        d["sub"].textContent = " · ".join(bits)
        d["btn"].setAttribute("data-key", str(r["seq"]))

    def btn_click(self, event):
        if self.parent:
            self.parent.raise_event("x-report", report=self.item)
