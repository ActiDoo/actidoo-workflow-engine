# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH

"""Rewriting FEEL-like expressions (hide-if conditions, gateway conditions) to Python.

The engine does not run a FEEL interpreter: an expression is rewritten by text
replacement and then parsed or evaluated as Python. This module is the one place that
does the rewriting, so hide-if and gateway conditions read an expression the same way.
"""

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
