# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""How workflow code reads a field that has no value.

An emptied form field is null in the task data, a field that was never filled has
no key. Workflow code should not have to tell the two apart: the value helper
returns a fallback for both (and for a blank text), and a mail template prints
both as nothing - never as "None".
"""

from types import SimpleNamespace

import pytest

from actidoo_wfe.wf.mail import compile_email_template
from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper, get_value


@pytest.mark.parametrize("data", [{}, {"comment": None}, {"comment": ""}, {"comment": "  \n"}])
def test__no_value_gives_the_fallback(data):
    assert get_value(data, "comment") == ""
    assert get_value(data, "comment", "no comment") == "no comment"
    assert get_value(data, "comment", None) is None


@pytest.mark.parametrize("value", ["text", "  padded  ", 0, False, [], {"id": "1"}])
def test__a_value_is_returned_unchanged(value):
    """Only null and blank text count as no value: zero, false and an empty list
    are answers."""
    assert get_value({"field": value}, "field", "fallback") == value


def test__the_helper_reads_the_task_data():
    sth = SimpleNamespace(task_data={"comment": None, "title": "Offer"})

    assert ServiceTaskHelper.get_value(sth, "comment", "-") == "-"
    assert ServiceTaskHelper.get_value(sth, "title") == "Offer"


def test__a_mail_template_prints_a_missing_value_as_nothing(tmp_path):
    (tmp_path / "mail.mako").write_text("[${empty}][${zero}][${flag}][${text}][${escaped | h}]")

    rendered = compile_email_template(
        "mail.mako",
        {"empty": None, "zero": 0, "flag": False, "text": "a & b", "escaped": None},
        template_dir=tmp_path,
    )

    assert rendered == "[][0][False][a & b][]"


def test__a_mail_template_still_rejects_a_value_nobody_passed(tmp_path):
    """The filter is about values that are there but empty; a name the template
    uses without it being passed is still an error."""
    (tmp_path / "mail.mako").write_text("${typo}")

    with pytest.raises(NameError):
        compile_email_template("mail.mako", {}, template_dir=tmp_path)
