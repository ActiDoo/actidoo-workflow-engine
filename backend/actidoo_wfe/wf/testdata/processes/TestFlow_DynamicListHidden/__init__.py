# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Test process for a required field inside a hidden nested dynamic list.

One user task with a select that drives three dynamic lists. The outer list
holds a text field and a nested inner list whose only field is required; the
inner list is hidden while the select is ``yes`` or unset. A third list is
hidden while the select is ``no`` or unset. Every list starts with one default
row, so the hidden inner list always carries an empty required field when the
form is submitted with ``yes`` - a submission that must not be blocked.
"""
