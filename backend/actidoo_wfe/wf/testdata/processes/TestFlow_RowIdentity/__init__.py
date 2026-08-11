# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Manual-test process for dynamic-list row identity (ADR 010).

Three user tasks share one dynamic list. The first captures rows with every
field editable; the second renders ``backend_value`` as a disabled field
carrying a default (a forced assignment) and hides ``hidden_note`` per item;
the third shows the stored result read-only. That combination exercises
deleting, adding, copying and reordering rows against the per-row restore of
hidden and backend-owned values.
"""
