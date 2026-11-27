# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Manual comparison of form submissions on main and fix/form-semantics.

After each successful submit a service task reports the values the manual cases ask about.
Keeping ``again`` selected opens another task with that report at the top, so
the tester can check what happened to a value across several submissions.
"""

import json

from actidoo_wfe.wf.service_task_helper import ServiceTaskHelper

RECORD_KEY = "service_saw"


def service_prepare_cases(sth: ServiceTaskHelper):
    sth.set_task_data(
        {
            "date_optional": "2026-01-31",
            "datetime_optional": "2026-01-31T10:00:00.000Z",
            "text_optional": "Sample",
            "tags_optional": [],
            "file_optional": None,
            "amount": 10,
            "finding": "true_positive",
            "positions": [{"item": "Pen"}],
            "overview_rows": [{"overview_item": "Pen", "overview_note": "Sample note"}],
            "locked_text": "set by the service task",
            "locked_rows": [{"locked_item": "set by the service task"}],
            "locked_code": "ABC",
            "kept_reason": "Stored reason",
        }
    )


def service_record_received(sth: ServiceTaskHelper):
    data = sth.task_data
    missing = object()
    upload = data.get("file_optional", missing)
    rows = data.get("positions") or []
    results = {
        "2. Stored date": data.get("date_optional", missing),
        "2b. Stored date with time": data.get("datetime_optional", missing),
        "6. Replacement file": upload.get("filename", missing) if isinstance(upload, dict) else upload,
        "7. Note": data.get("note_unless_a", missing),
        "8. Reason": data.get("reason_up_to_10", missing),
        "9. Finding details": data.get("finding_details", missing),
        "10a. Row note": rows[0].get("note", missing) if rows else missing,
        "11b. Read-only code": data.get("locked_code", missing),
        "13. Reason to keep": data.get("kept_reason", missing),
    }
    report = "\n".join(f"{label} = {'(missing)' if value is missing else json.dumps(value, ensure_ascii=False)}" for label, value in results.items())
    sth.set_task_data({RECORD_KEY: report})
    if data.get("store_long_code"):
        sth.set_task_data({"locked_code": "ABCDEF", "store_long_code": False})
