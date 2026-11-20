// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { evaluate, InterpreterContext, parseExpression, parseUnaryTests, unaryTest } from 'feelin';

const MAX_RESULTS_PER_EXPRESSION = 1000;
const MAX_VALUES_KEY_LENGTH = 10000;

// Calls may depend on time. Comments and quoted names need FEEL's full name resolution.
const UNCACHED_NODES = new Set([
  'FunctionInvocation',
  'FunctionDefinition',
  'DateTimeConstructor',
  'BacktickIdentifier',
  'LineComment',
  'BlockComment',
]);

interface Dependencies {
  words: Set<string>;
  compactExpression: string;
}

function getDependencies(parse: typeof parseExpression, expression: string): Dependencies | null {
  let cacheable = true;
  try {
    parse(expression).iterate({
      enter: ({ type }) => {
        if (type.isError || UNCACHED_NODES.has(type.name)) {
          cacheable = false;
        }
      },
    });
  } catch {
    return null;
  }
  if (!cacheable) return null;

  // FEEL parses names against the current context. A context-free syntax tree
  // sees subtraction in "order-total" and a literal in "true", but either may
  // be a field. Keep all words that could name an input, including keywords.
  return {
    words: new Set(expression.match(/[a-zA-Z0-9_]+/g)),
    compactExpression: expression.replace(/\s/g, ''),
  };
}

function valuesKey(
  { words, compactExpression }: Dependencies,
  context: InterpreterContext
): string {
  const fields = Object.keys(context).filter(name => {
    if (name === '?') return true;
    if (/^[a-zA-Z0-9_]+$/.test(name)) return words.has(name);
    // FEEL also matches compound names with different spacing, e.g. "order - total".
    return compactExpression.includes(name.replace(/\s/g, ''));
  });
  // Include the actual names in lookup order: adding "order-total" can change
  // the meaning even when "order" and "total" retain their values.
  const entries = fields.map(name => [name, context[name]]);
  // Tag strings so a literal value cannot collide with the encoding of undefined.
  return JSON.stringify(entries, (_key, value) => {
    if (typeof value === 'string') return `s${value}`;
    if (value === undefined) return 'undefined';
    return value;
  });
}

function memoize<T>(
  parse: typeof parseExpression,
  run: (expression: string, context: InterpreterContext) => T
): (expression: string, context?: InterpreterContext) => T {
  const dependenciesByExpression = new Map<string, Dependencies | null>();
  const resultsByExpression = new Map<string, Map<string, T>>();

  return (expression, context = {}) => {
    let dependencies = dependenciesByExpression.get(expression);
    if (dependencies === undefined) {
      dependencies = getDependencies(parse, expression);
      dependenciesByExpression.set(expression, dependencies);
    }
    if (!dependencies) return run(expression, context);

    const key = valuesKey(dependencies, context);
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
