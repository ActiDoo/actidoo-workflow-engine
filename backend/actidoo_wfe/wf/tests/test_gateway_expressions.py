# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""How FEEL expressions (a leading ``=``) read the task data.

A sequence-flow condition reads a field the data does not hold - never filled, or
hidden - as null, the way FEEL and a form's hide-if read it, so the gateway routes
instead of failing the task. Every other expression stays strict: a missing name in
a collection, a timer or a correlation key is a modelling error and must surface.
``null`` is the FEEL literal everywhere; ``None`` keeps working too. Expressions
without a leading ``=`` are plain Python and unchanged.
"""

from types import SimpleNamespace

import pytest
from SpiffWorkflow.bpmn.script_engine.python_environment import TaskDataEnvironment
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.util.task import TaskState

import actidoo_wfe.wf.service_workflow  # noqa: F401 - settles the import order of spiff_customized
from actidoo_wfe.wf.spiff_customized import MyScriptEngine, get_parser, get_serializer


def _engine(**env_globals) -> MyScriptEngine:
    return MyScriptEngine(environment=TaskDataEnvironment(env_globals))


def _condition(expression: str, data: dict, **env_globals):
    return _engine(**env_globals).evaluate_condition(SimpleNamespace(data=data), expression)


def _expression(expression: str, data: dict):
    return _engine().evaluate(SimpleNamespace(data=data), expression)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("=approval = null", True),
        ("=approval != null", False),
        ('=approval = "yes"', False),
        ('=approval != "yes"', True),
        ('=approval = "yes" or fallback = "yes"', True),
    ],
)
def test__a_condition_reads_a_missing_field_as_null(expression, expected):
    """The field was never filled or is hidden: no key in the data. The condition
    sees null - a comparison against a value is false, one against null is true."""
    assert _condition(expression, {"fallback": "yes"}) is expected


def test__a_condition_compares_a_present_field_as_before():
    assert _condition('=approval = "yes"', {"approval": "yes"}) is True
    assert _condition('=approval = "yes"', {"approval": "no"}) is False
    assert _condition("=amount > 1000", {"amount": 5}) is False


def test__null_and_none_are_the_same_literal():
    """Older workflows write ``None`` and ``is None`` the Python way; ``null`` is
    the FEEL spelling. Both mean the missing value, and an emptied field holds null."""
    assert _condition("=approver = None", {}) is True
    assert _condition("=approver is None", {}) is True
    assert _condition("=approver = null", {"approver": None}) is True
    assert _condition("=approver = null", {"approver": "x"}) is False


def test__null_inside_a_string_literal_is_text():
    assert _condition('=status = "null"', {"status": "null"}) is True
    assert _condition("=status = 'null'", {"status": "null"}) is True


@pytest.mark.parametrize("text", ["true_positive", "a=b", "false alarm"])
def test__text_in_quotes_is_compared_as_written(text):
    """The rewrite to Python leaves text in quotes alone - it used to turn
    "true_positive" into "True_positive" and "a=b" into "a==b"."""
    assert _condition(f'=kind = "{text}"', {"kind": text}) is True


def test__names_containing_true_or_false_are_left_alone():
    """Only the whole word true or false is the FEEL literal."""
    assert _condition("=is_true_flag = true", {"is_true_flag": True}) is True
    assert _condition("=falsely_marked = false", {"falsely_marked": False}) is True


def test__the_globals_guard_of_older_workflows_keeps_working():
    assert _condition('="approver" not in globals() or approver is None', {}) is True
    assert _condition('="approver" not in globals() or approver is None', {"approver": "x"}) is False


def test__builtins_and_workflow_functions_are_still_reachable():
    """Only names the data does not hold read as null; builtins, Spiff's FEEL
    helpers and the workflow module's functions resolve as before."""
    assert _condition("=len(items) = 2", {"items": [1, 2]}) is True
    assert _condition("=flag = true", {"flag": True}) is True
    assert _condition('=label() = "x"', {}, label=lambda: "x") is True


def test__any_other_expression_stays_strict_about_missing_names():
    """A collection, a timer or a correlation key naming a variable that does not
    exist fails loudly instead of continuing with null."""
    with pytest.raises(NameError):
        _expression("=items", {})
    assert _expression("=items", {"items": [1]}) == [1]


def test__any_other_expression_understands_the_null_literal():
    assert _expression("=reference = null", {"reference": None}) is True


def test__a_python_condition_stays_strict():
    """Without the leading ``=`` the condition is Python, and a missing name is
    an error - nothing changes for these."""
    with pytest.raises(Exception, match="approval"):
        _condition("approval == 'yes'", {})


GATEWAY_BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_gateway" targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="GatewayOnMissingField" isExecutable="true">
    <bpmn:laneSet id="lanes">
      <bpmn:lane id="lane" name="Initiator">
        <bpmn:flowNodeRef>start</bpmn:flowNodeRef>
        <bpmn:flowNodeRef>gateway</bpmn:flowNodeRef>
        <bpmn:flowNodeRef>skipped</bpmn:flowNodeRef>
        <bpmn:flowNodeRef>approval</bpmn:flowNodeRef>
      </bpmn:lane>
    </bpmn:laneSet>
    <bpmn:startEvent id="start">
      <bpmn:outgoing>to_gateway</bpmn:outgoing>
    </bpmn:startEvent>
    <bpmn:sequenceFlow id="to_gateway" sourceRef="start" targetRef="gateway" />
    <bpmn:exclusiveGateway id="gateway" default="to_approval">
      <bpmn:incoming>to_gateway</bpmn:incoming>
      <bpmn:outgoing>to_skip</bpmn:outgoing>
      <bpmn:outgoing>to_approval</bpmn:outgoing>
    </bpmn:exclusiveGateway>
    <bpmn:sequenceFlow id="to_skip" sourceRef="gateway" targetRef="skipped">
      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">=approver = null</bpmn:conditionExpression>
    </bpmn:sequenceFlow>
    <bpmn:sequenceFlow id="to_approval" sourceRef="gateway" targetRef="approval" />
    <bpmn:endEvent id="skipped">
      <bpmn:incoming>to_skip</bpmn:incoming>
    </bpmn:endEvent>
    <bpmn:endEvent id="approval">
      <bpmn:incoming>to_approval</bpmn:incoming>
    </bpmn:endEvent>
  </bpmn:process>
</bpmn:definitions>
"""


def _gateway_workflow(data: dict, restored: bool) -> BpmnWorkflow:
    parser = get_parser()
    parser.add_bpmn_str(GATEWAY_BPMN.encode())
    workflow = BpmnWorkflow(parser.get_spec("GatewayOnMissingField"), script_engine=_engine())
    if restored:
        # A stored instance rebuilds its conditions from the serialized form.
        serializer = get_serializer()
        workflow = serializer.from_dict(serializer.to_dict(workflow))
        workflow.script_engine = _engine()
    workflow.task_tree.set_data(**data)
    return workflow


def _reached_end(workflow: BpmnWorkflow) -> str:
    workflow.do_engine_steps()
    assert workflow.is_completed()
    ends = {"skipped", "approval"}
    return next(t.task_spec.bpmn_id for t in workflow.get_tasks(state=TaskState.COMPLETED) if t.task_spec.bpmn_id in ends)


@pytest.mark.parametrize("restored", [False, True])
def test__a_gateway_on_a_field_that_was_never_filled_routes(restored):
    """End to end, also for an instance loaded from storage: the approver field is
    missing, so ``approver = null`` holds and the approval is skipped."""
    assert _reached_end(_gateway_workflow({}, restored)) == "skipped"
    assert _reached_end(_gateway_workflow({"approver": None}, restored)) == "skipped"
    assert _reached_end(_gateway_workflow({"approver": "a@example.com"}, restored)) == "approval"
