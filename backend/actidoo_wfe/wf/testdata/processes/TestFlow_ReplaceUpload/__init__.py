# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Test process for replacing an optional single upload.

Three user tasks share the same form: an optional single upload outside a dynamic
list and one inside its rows. The steps upload a file, remove it and upload another
one, so a new file lands on a field whose stored value is null.
"""
