# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Test process for a select with ``depends_on``, at the top level and inside a dynamic list."""

SUB_TYPES = {
    "car": [("sedan", "Sedan"), ("suv", "SUV"), ("convertible", "Convertible")],
    "truck": [("pickup", "Pickup"), ("semi", "Semi-trailer"), ("dump", "Dump truck")],
}


def get_car_sub_type_options(oth):
    return SUB_TYPES.get(oth.get_form_field_environment().get("car_type"), [])
