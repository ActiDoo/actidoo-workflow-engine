# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

# Test workflow that exercises the CurrencyNumberWidget. The form has three
# number fields:
#   - amount_eur:  triggered via appearance.suffixAdorner = "€"
#   - amount_usd:  triggered via custom_properties.currency = "USD"
#   - weight_kg:   plain number with kg suffix (NOT triggered — control case)
pass
