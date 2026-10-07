# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Test process for a field that a later step hides.

Three user tasks share the optional text field ``text_a`` and the optional multi
select ``tags_a``, both with a default. The first step shows them, the second hides
them while ``flag_a`` is true, the third shows them again.
"""
