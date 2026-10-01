# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Rewriting FEEL-like expressions (hide-if conditions, gateway conditions) to Python.

The engine does not run a FEEL interpreter: an expression is rewritten by text
replacement and then parsed or evaluated as Python. This module is the one place that
does the rewriting, so hide-if and gateway conditions read an expression the same way.
"""

import ast
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
    python = re.sub(r"(?<!=|<|>|\!)=(?!=|<|>|\!)", "==", python)
    python = re.sub(r"\bnull\b", "None", python)
    return _PLACEHOLDER.sub(lambda match: texts[int(match.group(1))], python)


_ORDERING_OPERATORS = {"Lt": operator.lt, "LtE": operator.le, "Gt": operator.gt, "GtE": operator.ge}


def compare_ordered_values(left, right, operation):
    """An ordering comparison cannot match null; incompatible real values still fail."""
    if left is None or right is None:
        return False
    return _ORDERING_OPERATORS[operation](left, right)


def compile_feel_condition(expression: str, scope: dict):
    """Compile null-safe ordering comparisons and put their helper in the evaluation scope.

    Splitting a chain retains short-circuiting and evaluates its middle operands
    once. Generated names cannot shadow names used by the expression or context.
    """
    tree = ast.parse(feel_to_python(expression), mode="eval")
    reserved_names = set(scope) | {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    ordering_function_name = "__wfe_ordering_compare"
    while ordering_function_name in reserved_names:
        ordering_function_name += "_"
    scope[ordering_function_name] = compare_ordered_values
    reserved_names.add(ordering_function_name)

    class NullSafeOrdering(ast.NodeTransformer):
        def visit_Compare(self, node):
            node = self.generic_visit(node)
            if not any(type(op).__name__ in _ORDERING_OPERATORS for op in node.ops):
                return node
            parts = []
            left = node.left
            for index, (op, right) in enumerate(zip(node.ops, node.comparators)):
                next_left = right
                if index < len(node.ops) - 1:
                    # In a < f() < b, save f() once for the next comparison.
                    name = "__wfe_comparison_value"
                    while name in reserved_names:
                        name += "_"
                    reserved_names.add(name)
                    right = ast.NamedExpr(target=ast.Name(id=name, ctx=ast.Store()), value=right)
                    next_left = ast.Name(id=name, ctx=ast.Load())
                # Only ordering needs a null check; equality and membership keep Python's rules.
                if type(op).__name__ in _ORDERING_OPERATORS:
                    part = ast.Call(
                        func=ast.Name(id=ordering_function_name, ctx=ast.Load()),
                        args=[left, right, ast.Constant(value=type(op).__name__)],
                        keywords=[],
                    )
                else:
                    part = ast.Compare(left=left, ops=[op], comparators=[right])
                parts.append(part)
                left = next_left
            # AND preserves a chain's short-circuiting: later operands run only if needed.
            return parts[0] if len(parts) == 1 else ast.BoolOp(op=ast.And(), values=parts)

    tree = ast.fix_missing_locations(NullSafeOrdering().visit(tree))
    return compile(tree, "<FEEL condition>", "eval")
