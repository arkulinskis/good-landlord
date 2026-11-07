from anvil import *

from ._anvil_designer import RentChipTemplate
from ... import gl


class RentChip(RentChipTemplate):
    """Tenancy record: a month of rent received ("Oct 26"). item = {month: 'YYYY-MM', amount, date}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.dom_nodes["chip"].textContent = gl.month_name(r["month"], True) + " " + r["month"][2:4]
        self.dom_nodes["chip"].setAttribute("title", gl.money(r["amount"]) + " on " + (r.get("date") or ""))
