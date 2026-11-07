from anvil import *

from ._anvil_designer import ReceiptRowTemplate
from ... import gl


class ReceiptRow(ReceiptRowTemplate):
    """Tenant page: rent the landlord recorded as received. item = {month, amount, date}"""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.dom_nodes["month"].textContent = gl.month_name(r["month"])
        self.dom_nodes["paid"].textContent = gl.money(r["amount"], cents=True) + " · " + gl.fmt_date(r["date"], "dm")
