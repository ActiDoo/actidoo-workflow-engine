# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from actidoo_wfe.wf import service_workflow  # noqa: F401 - initialize the workflow modules before the task specs
from actidoo_wfe.wf.spiff_customized import MyIntermediateThrowEvent, MyScriptEngine, MyServiceTask, TaskDataEnvironment


@pytest.mark.parametrize("task_type", [MyServiceTask, MyIntermediateThrowEvent])
@pytest.mark.parametrize("previous_data", [{}, {"result_Lookup": {"id": 42}}])
def test_empty_service_result_overwrites_previous_result_and_can_be_read_by_gateway(task_type, previous_data):
    """An empty result remains readable as null, including after a previous non-empty result."""
    spec = object.__new__(task_type)
    spec.service_type = "lookup"
    task = SimpleNamespace(
        data=dict(previous_data),
        task_spec=SimpleNamespace(name="Lookup"),
        workflow=SimpleNamespace(script_engine=SimpleNamespace(call_service=Mock(return_value=b"null"))),
    )

    assert spec._execute(task) is True
    assert task.data["result_Lookup"] is None
    engine = MyScriptEngine(TaskDataEnvironment({}))
    assert engine._evaluate("=result_Lookup = None", task.data) is True
