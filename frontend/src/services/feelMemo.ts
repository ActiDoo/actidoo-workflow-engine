// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { evaluate, InterpreterContext, parseExpression, parseUnaryTests, unaryTest } from 'feelin';

const MAX_RESULTS_PER_EXPRESSION = 1000;
const MAX_VALUES_KEY_LENGTH = 10000;
const MISSING_FIELD = '\u0000missing';
const UNDEFINED_VALUE = '\u0000undefined';

function referencedNames(parse: typeof parseExpression, expression: string): string[] | null {
  let memoizable = true;
  const names = new Set<string>(['?']);
  try {
    parse(expression).iterate({
      enter: node => {
        if (node.type.isError || node.type.name === 'FunctionInvocation') {
          memoizable = false;
        } else if (node.type.name === 'VariableName') {
          names.add(expression.slice(node.from, node.to));
        }
      },
    });
  } catch {
    memoizable = false;
  }
  return memoizable ? [...names] : null;
}

function valuesKey(names: string[], context: InterpreterContext): string {
  const values = names.map(name => (name in context ? context[name] : MISSING_FIELD));
  return JSON.stringify(values, (_key, value) => (value === undefined ? UNDEFINED_VALUE : value));
}

function memoize<T>(
  parse: typeof parseExpression,
  run: (expression: string, context: InterpreterContext) => T
): (expression: string, context?: InterpreterContext) => T {
  const namesByExpression = new Map<string, string[] | null>();
  const resultsByExpression = new Map<string, Map<string, T>>();

  return (expression, context = {}) => {
    let names = namesByExpression.get(expression);
    if (names === undefined) {
      names = referencedNames(parse, expression);
      namesByExpression.set(expression, names);
    }
    if (!names) {
      return run(expression, context);
    }

    const key = valuesKey(names, context);
    if (key.length > MAX_VALUES_KEY_LENGTH) {
      return run(expression, context);
    }

    let results = resultsByExpression.get(expression);
    if (!results) {
      results = new Map();
      resultsByExpression.set(expression, results);
    }
    if (results.has(key)) {
      return results.get(key) as T;
    }

    const result = run(expression, context);
    if (results.size >= MAX_RESULTS_PER_EXPRESSION) {
      results.clear();
    }
    results.set(key, result);
    return result;
  };
}

export const memoizedUnaryTest = memoize<boolean>(parseUnaryTests, unaryTest);
export const memoizedEvaluate = memoize<any>(parseExpression, evaluate);
