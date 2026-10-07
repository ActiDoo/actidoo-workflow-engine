# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""How FEEL expressions (a leading ``=``) read the task data.

A sequence-flow condition reads a field the data does not hold - never filled, or
hidden - as null, the way FEEL and a form's hide-if read it, so the gateway routes
instead of failing the task. As in a hide-if, a comparison with null or ``""`` matches
every empty value: no key, null, blank text and an empty list. Every other expression
stays strict: a missing name in a collection, a timer or a correlation key is a
modelling error and must surface. ``null`` is the FEEL literal everywhere; ``None``
keeps working too. A condition the engine cannot translate correctly fails with a
message instead of routing. Expressions without a leading ``=`` are plain Python and
unchanged.
"""

from types import SimpleNamespace

import pytest
from SpiffWorkflow.bpmn.script_engine.python_environment import TaskDataEnvironment
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.util.task import TaskState

from actidoo_wfe.wf import service_workflow  # also settles the import order of spiff_customized
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


@pytest.mark.parametrize(
    "expression",
    [
        "=amount < 10",
        "=amount <= 10",
        "=amount > 10",
        "=amount >= 10",
        "=10 < amount",
        "=10 <= amount",
        "=10 > amount",
        "=10 >= amount",
        "=0 < amount < 10",
    ],
)
@pytest.mark.parametrize("data", [{}, {"amount": None}])
def test__ordering_a_missing_or_null_value_is_false(expression, data):
    """An unanswered amount cannot satisfy an ordering comparison or fail a gateway."""
    assert _condition(expression, data) is False


def test__a_null_ordering_comparison_does_not_skip_the_other_boolean_operand():
    """A null comparison is false locally, so a matching fallback still routes."""
    assert _condition('=amount > 10 or fallback = "yes"', {"fallback": "yes"}) is True
    assert _condition('=amount > 10 and fallback = "yes"', {"fallback": "yes"}) is False


def test__a_typo_still_reads_as_null_in_equality_comparisons():
    """Null equality and inequality can be true; typos are not always false."""
    assert _condition("=aprover = null", {}) is True
    assert _condition('=aprover != "yes"', {}) is True


def test__ordering_keeps_python_short_circuiting_and_evaluates_each_operand_once():
    """Chained comparisons do not call the last operand after an earlier false result."""
    calls = []

    def middle():
        calls.append("middle")
        return 5

    def last():
        calls.append("last")
        return 10

    assert _condition("=0 < middle() < last()", {}, middle=middle, last=last) is True
    assert calls == ["middle", "last"]
    calls.clear()
    assert _condition("=amount < middle() < last()", {}, middle=middle, last=last) is False
    assert calls == ["middle"]


def test__ordering_real_incompatible_values_still_fails():
    with pytest.raises(TypeError):
        _condition("=amount > 10", {"amount": "invalid"})


def test__null_and_none_are_the_same_literal():
    """Older workflows write ``None`` and ``is None`` the Python way; ``null`` is
    the FEEL spelling. Both mean the missing value, and an emptied field holds null."""
    assert _condition("=approver = None", {}) is True
    assert _condition("=approver is None", {}) is True
    assert _condition("=approver = null", {"approver": None}) is True
    assert _condition("=approver = null", {"approver": "x"}) is False


EMPTY_VALUES = [{}, {"comment": None}, {"comment": ""}, {"comment": "   "}]


@pytest.mark.parametrize("data", EMPTY_VALUES)
@pytest.mark.parametrize("expression", ["=comment = null", '=comment = ""', '="" = comment', "=comment is None"])
def test__a_comparison_with_null_or_empty_text_matches_every_empty_value(expression, data):
    """The comment was never filled (no key), emptied (null), or older data holds
    blank text. A comparison with null or "" treats them all as empty, as a form's
    hide-if does."""
    assert _condition(expression, data) is True


@pytest.mark.parametrize("data", EMPTY_VALUES)
@pytest.mark.parametrize("expression", ["=comment != null", '=comment != ""', '="comment" in globals() and comment != ""'])
def test__a_check_for_a_value_is_false_for_every_empty_value(expression, data):
    """The other direction, including the guard older workflows use."""
    assert _condition(expression, data) is False


def test__a_check_for_a_value_holds_for_a_value():
    assert _condition('=comment != ""', {"comment": "x"}) is True
    assert _condition('="comment" in globals() and comment != ""', {"comment": "x"}) is True
    assert _condition('=comment = ""', {"comment": "x"}) is False


def test__an_empty_list_reads_as_null():
    """A multi select with nothing chosen is empty, as in a form's hide-if."""
    assert _condition("=tags = null", {"tags": []}) is True
    assert _condition("=tags != null", {"tags": ["a"]}) is True


@pytest.mark.parametrize("data", [{"amount": ""}, {"amount": "  "}])
def test__ordering_a_blank_value_is_false(data):
    """Blank text reads as null, so an ordering comparison with it is false."""
    assert _condition("=amount > 10", data) is False


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


@pytest.mark.parametrize("name", ["type", "id", "zip", "max", "format", "license", "input", "property"])
def test__a_missing_field_named_like_a_builtin_reads_as_null(name):
    """Fields called type or id are common. Missing, such a field is null like any
    other missing field, not the Python builtin of that name."""
    assert _condition(f"={name} = null", {}) is True
    assert _condition(f"={name} != null", {}) is False
    assert _condition(f"={name} > 5", {}) is False
    assert not _condition(f"={name}", {})


def test__a_builtin_is_reached_by_calling_it():
    """A call such as max(a, b) still reaches the builtin, and a field the data holds
    wins over a builtin of the same name."""
    assert _condition("=max(a, b) = 3", {"a": 1, "b": 3}) is True
    assert _condition("=any(x > 1 for x in items)", {"items": [1, 2]}) is True
    assert _condition('=type = "invoice"', {"type": "invoice"}) is True


@pytest.mark.parametrize("expression", ["=isinstance(amount, int)", "=isinstance(amount, (int, float))", '=list(map(str, tags)) = ["1", "2"]'])
def test__builtins_remain_available_as_function_arguments(expression):
    assert _condition(expression, {"amount": 2, "tags": [1, 2]}) is True


@pytest.mark.parametrize("expression", ["=any(len(x) = 99 for len in funcs)", "=all([len(x) = 99 for len in funcs])", "=any(len(x) = 99 for len in funcs if len(x) = 99)", "=(lambda len: len(x))(funcs[0]) = 99"])
def test__local_bindings_take_precedence_over_builtins(expression):
    assert _condition(expression, {"funcs": [lambda x: 99], "x": "a"}) is True


def test__a_local_binding_does_not_shadow_a_builtin_outside_its_scope():
    assert _condition("=any(len(x) = 99 for len in funcs) and len(x) = 1", {"funcs": [lambda x: 99], "x": "a"}) is True
    assert _condition("=isinstance(amount, int)", {"amount": 2, "int": str}) is False


@pytest.mark.parametrize(
    "expression",
    [
        "=not(approved = true)",
        "=approved = true and not(rejected = true)",
        '=not contains("a")',
        '=contains("a")',
        "=amount in [1..5]",
        "=amount in (1..5]",
    ],
)
def test__a_condition_the_engine_cannot_translate_fails_instead_of_routing(expression):
    """not(...), contains(...) with one argument and ranges become objects that only
    compare correctly with = or !=. Anywhere else they were always true, or - an open
    range, 'not contains' - compared the wrong way without a word. Now the condition
    fails with a message saying what to write instead."""
    with pytest.raises(ValueError, match="Cannot evaluate the condition .* only works on one side of = or !=; write"):
        _condition(expression, {"approved": True, "rejected": False, "amount": 3})


@pytest.mark.parametrize(
    ("expression", "amount", "expected"),
    [
        ("=amount = (1..5]", 1, False),
        ("=amount = (1..5]", 5, True),
        ("=amount = [1..5)", 5, False),
        ("=amount = [1..5)", 1, True),
        ("=amount != (1..5]", 1, True),
    ],
)
def test__a_range_on_one_side_of_an_equality_keeps_its_open_ends(expression, amount, expected):
    """With = or != a range works, and an open end stays open - it used to read as closed."""
    assert _condition(expression, {"amount": amount}) is expected


def test__not_contains_with_two_arguments_is_a_plain_negation():
    assert _condition('=not contains(comment, "x")', {"comment": "abc"}) is True
    assert _condition('=not contains(comment, "a")', {"comment": "abc"}) is False


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


def _gateway_workflow(data: dict, restored: bool, condition: str = "=approver = null") -> BpmnWorkflow:
    parser = get_parser()
    parser.add_bpmn_str(GATEWAY_BPMN.replace("=approver = null", condition).encode())
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


@pytest.mark.parametrize("restored", [False, True])
def test__a_gateway_on_a_blank_value_routes_like_on_an_empty_field(restored):
    """Older data can hold blank text where an emptied field is null today."""
    for data in [{"approver": ""}, {"approver": "  "}]:
        assert _reached_end(_gateway_workflow(data, restored, '=approver = ""')) == "skipped"
    assert _reached_end(_gateway_workflow({"approver": "a@example.com"}, restored, '=approver = ""')) == "approval"


@pytest.mark.parametrize("restored", [False, True])
def test__a_gateway_whose_condition_cannot_be_translated_goes_to_error(restored):
    """The engine puts the gateway in error, where an administrator sees the message
    and can retry once the model is fixed, instead of taking a route."""
    workflow = _gateway_workflow({}, restored, "=not(approver = null)")

    assert service_workflow.run_workflow(workflow) is False
    faulty = service_workflow.get_faulty_tasks(workflow)
    assert [task.task_spec.bpmn_id for task in faulty] == ["gateway"]
    assert "Cannot evaluate the condition 'not(approver = null)'" in service_workflow.get_stacktrace(workflow, faulty[0].id)


@pytest.mark.parametrize("restored", [False, True])
def test__a_gateway_ordering_an_unanswered_amount_routes_to_its_default(restored):
    """New and restored instances take the default route for a missing or cleared amount."""
    for data in [{}, {"amount": None}, {"amount": 5}]:
        assert _reached_end(_gateway_workflow(data, restored, "=amount > 10")) == "approval"
    assert _reached_end(_gateway_workflow({"amount": 20}, restored, "=amount > 10")) == "skipped"
