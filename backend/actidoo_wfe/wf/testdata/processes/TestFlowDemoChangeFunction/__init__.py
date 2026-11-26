# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""TestFlowDemoChangeFunction — form values derived by change functions.

The first task derives the disabled price of each gift row from the row's product and
the company, suggests an editable remark, and fills two disabled contact fields from a
product select; the second task shows the stored values read-only.
"""

PRICES = {"pen": 2.0, "mug": 10.0, "backpack": 40.0}
SURCHARGE = {"subsidiary": 1.1}
REMARKS = {"pen": "blue ink", "mug": "dishwasher safe", "backpack": "20 litres"}
CONTACTS = {
    "pisco": ("Camila Rojas", "CCC Spirits"),
    "wine": ("Matias Soto", "CCC Wine"),
    "olive_oil": ("Valentina Diaz", "CCC Food"),
}


def _price(product, company):
    if product not in PRICES:
        return None
    return round(PRICES[product] * SURCHARGE.get(company, 1), 2)


def update_prices(cth):
    for row in cth.form_data.get("gifts") or []:
        row["price"] = _price(row.get("product"), cth.value)


def update_gift(cth):
    cth.row["price"] = _price(cth.value, cth.form_data.get("company"))
    if not cth.row.get("remark"):
        cth.row["remark"] = REMARKS.get(cth.value)


def update_contacts(cth):
    cth.form_data["product_manager"], cth.form_data["ccc_group"] = CONTACTS.get(cth.value, (None, None))
