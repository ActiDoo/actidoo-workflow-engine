# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Rewriting FEEL-like expressions (hide-if conditions, gateway conditions) to Python.

The engine does not run a FEEL interpreter: an expression is rewritten by text
replacement and then parsed or evaluated as Python. This module is the one place that
does the rewriting, so hide-if and gateway conditions read an expression the same way.
"""

import ast
import builtins
import operator
import re

from SpiffWorkflow.bpmn.script_engine.feel_engine import fixes as _spiff_fixes

# Text in quotes is set aside before rewriting and put back unchanged afterwards - a
# condition comparing with "true_positive" or "a=b" means exactly that text.
_TEXT_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
_PLACEHOLDER = re.compile(r"__wfe_text_(\d+)__")

# Spiff rewrites true/false with a plain text replacement, which also changes names
# such as is_true_flag; only the whole word is the FEEL literal.
_FIXES = [(r"\btrue\b", "True") if fix == ("true", "True") else (r"\bfalse\b", "False") if fix == ("false", "False") else fix for fix in _spiff_fixes]

# Spiff writes ranges such as (1..5] and 'not contains(...)' as calls with these keyword
# arguments. Their '=' is no comparison, so they are set aside like text in quotes.
_SPIFF_KEYWORD_ARGUMENT = re.compile(r",(?:leftOpen|rightOpen|invert)=True\b")


def feel_to_python(expression: str) -> str:
    """Rewrite a FEEL-like expression to Python: Spiff's FEEL rewrites (functions,
    ``true``/``false``), a single ``=`` as ``==``, and the literal ``null`` as ``None``.
    Text in quotes stays exactly as written."""
    texts: list[str] = []

    def set_aside(match: re.Match) -> str:
        texts.append(match.group(0))
        return f"__wfe_text_{len(texts) - 1}__"

    python = _TEXT_LITERAL.sub(set_aside, expression)
    for pattern, replacement in _FIXES:
        if isinstance(replacement, str):
            python = re.sub(pattern, replacement, python)
        else:
            for found in re.findall(pattern, python):
                if "." in found:
                    python = python.replace(found, replacement(found))
    python = _SPIFF_KEYWORD_ARGUMENT.sub(set_aside, python)
    python = re.sub(r"(?<!=|<|>|\!)=(?!=|<|>|\!)", "==", python)
    python = re.sub(r"\bnull\b", "None", python)
    return _PLACEHOLDER.sub(lambda match: texts[int(match.group(1))], python)


_ORDERING_OPERATORS = {"Lt": operator.lt, "LtE": operator.le, "Gt": operator.gt, "GtE": operator.ge}
_EQUALITY_OPERATORS = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)


def reads_as_null(value) -> bool:
    """Whether a value reads as null in a condition, as in a form's hide-if: nothing,
    null, a blank text (empty or whitespace only) and an empty list - a multi select
    with nothing chosen."""
    return value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value)


def compare_ordered_values(left, right, operation):
    """An ordering comparison cannot match null, nor a value that reads as null;
    incompatible real values still fail."""
    if reads_as_null(left) or reads_as_null(right):
        return False
    return _ORDERING_OPERATORS[operation](left, right)


def _is_null_literal(node) -> bool:
    """``null`` (None after the rewrite) or ``""`` - an emptied field is null, so a
    comparison with "" means one with null."""
    return isinstance(node, ast.Constant) and (node.value is None or node.value == "")


# Spiff turns these FEEL forms into objects that only compare correctly with = or !=,
# as in 'x = [1..5]'. Anywhere else such an object is always true or fails obscurely.
_UNARY_TESTS = {
    "FeelNot": ("not(...)", "write 'x != 1' instead of 'not(x = 1)'"),
    "FeelContains": ("contains(...) with one argument", "write 'contains(x, \"a\")' or 'not contains(x, \"a\")'"),
    "FeelInterval": ("a range such as [1..5]", "write 'x >= 1 and x <= 5' instead of 'x in [1..5]'"),
}


def _reject_unary_tests_outside_comparisons(tree, expression: str) -> None:
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _UNARY_TESTS):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Compare) and len(parent.ops) == 1 and isinstance(parent.ops[0], (ast.Eq, ast.NotEq)):
            continue
        what, advice = _UNARY_TESTS[node.func.id]
        raise ValueError(f"Cannot evaluate the condition {expression!r}: {what} only works on one side of = or !=; {advice}.")


def compile_feel_condition(expression: str, scope: dict):
    """Compile a sequence-flow condition and put its helpers in the evaluation scope.

    A comparison with null or "" is true for every value that reads as null, and an
    ordering comparison with such a value is false. Python builtins remain available
    as functions and function arguments. A missing field called ``type`` or ``max``
    still reads as null when used as a field in a condition.
    Splitting a chain retains short-circuiting and evaluates its middle operands once.
    Generated names cannot shadow names used by the expression or context. A condition
    the rewrite cannot translate correctly raises instead of routing silently.
    """
    tree = ast.parse(feel_to_python(expression), mode="eval")
    _reject_unary_tests_outside_comparisons(tree, expression)
    reserved_names = set(scope) | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}

    def unique_name(name):
        while name in reserved_names:
            name += "_"
        reserved_names.add(name)
        return name

    ordering_function_name = unique_name("__wfe_ordering_compare")
    scope[ordering_function_name] = compare_ordered_values
    null_function_name = unique_name("__wfe_reads_as_null")
    scope[null_function_name] = reads_as_null
    builtins_name = unique_name("__wfe_builtins")
    scope[builtins_name] = builtins

    class CallBuiltins(ast.NodeTransformer):
        def __init__(self):
            self.bound = set()

        def builtin_value(self, node):
            if isinstance(node, ast.Name) and node.id not in scope and node.id not in self.bound and hasattr(builtins, node.id):
                return ast.Attribute(value=ast.Name(id=builtins_name, ctx=ast.Load()), attr=node.id, ctx=ast.Load())
            if isinstance(node, (ast.Tuple, ast.List)):
                node.elts = [self.builtin_value(item) for item in node.elts]
            return node

        def visit_Call(self, node):
            node = self.generic_visit(node)
            node.func = self.builtin_value(node.func)
            node.args = [self.builtin_value(arg) for arg in node.args]
            return node

        def visit_Lambda(self, node):
            # Defaults are evaluated outside the lambda's local scope.
            node.args = self.visit(node.args)
            outer = self.bound
            self.bound = outer | {arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
            self.bound |= {arg.arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None}
            node.body = self.visit(node.body)
            self.bound = outer
            return node

        def visit_GeneratorExp(self, node):
            # Only the first iterable runs outside the comprehension's local scope.
            node.generators[0].iter = self.visit(node.generators[0].iter)
            outer = self.bound
            self.bound = outer | {name.id for generator in node.generators for name in ast.walk(generator.target) if isinstance(name, ast.Name)}
            for index, generator in enumerate(node.generators):
                if index:
                    generator.iter = self.visit(generator.iter)
                generator.ifs = [self.visit(condition) for condition in generator.ifs]
            if isinstance(node, ast.DictComp):
                node.key = self.visit(node.key)
                node.value = self.visit(node.value)
            else:
                node.elt = self.visit(node.elt)
            self.bound = outer
            return node

        visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp

    def is_null_comparison(left, op, right):
        return isinstance(op, _EQUALITY_OPERATORS) and (_is_null_literal(left) or _is_null_literal(right))

    class NullSafeComparisons(ast.NodeTransformer):
        def visit_Compare(self, node):
            node = self.generic_visit(node)
            operands = [node.left, *node.comparators]
            if not any(type(op).__name__ in _ORDERING_OPERATORS or is_null_comparison(operands[index], op, operands[index + 1]) for index, op in enumerate(node.ops)):
                return node
            parts = []
            left = node.left
            for index, (op, right) in enumerate(zip(node.ops, node.comparators)):
                null_comparison = is_null_comparison(left, op, right)
                null_on_the_right = _is_null_literal(right)
                next_left = right
                if index < len(node.ops) - 1 and not isinstance(right, ast.Constant):
                    # In a < f() < b, save f() once for the next comparison.
                    name = unique_name("__wfe_comparison_value")
                    right = ast.NamedExpr(target=ast.Name(id=name, ctx=ast.Store()), value=right)
                    next_left = ast.Name(id=name, ctx=ast.Load())
                if type(op).__name__ in _ORDERING_OPERATORS:
                    part = ast.Call(
                        func=ast.Name(id=ordering_function_name, ctx=ast.Load()),
                        args=[left, right, ast.Constant(value=type(op).__name__)],
                        keywords=[],
                    )
                elif null_comparison:
                    # x = null, x = "", x is None: every value that reads as null matches.
                    part = ast.Call(
                        func=ast.Name(id=null_function_name, ctx=ast.Load()),
                        args=[left if null_on_the_right else right],
                        keywords=[],
                    )
                    if isinstance(op, (ast.NotEq, ast.IsNot)):
                        part = ast.UnaryOp(op=ast.Not(), operand=part)
                else:
                    # Other equality and membership keep Python's rules.
                    part = ast.Compare(left=left, ops=[op], comparators=[right])
                parts.append(part)
                left = next_left
            # AND preserves a chain's short-circuiting: later operands run only if needed.
            return parts[0] if len(parts) == 1 else ast.BoolOp(op=ast.And(), values=parts)

    tree = ast.fix_missing_locations(NullSafeComparisons().visit(CallBuiltins().visit(tree)))
    return compile(tree, "<FEEL condition>", "eval")
