// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import * as feelin from 'feelin';
import { memoizedEvaluate, memoizedUnaryTest } from '@/services/feelMemo';

vi.mock('feelin', async importOriginal => {
  const original = await importOriginal<typeof import('feelin')>();
  return {
    ...original,
    unaryTest: vi.fn(original.unaryTest),
    evaluate: vi.fn(original.evaluate),
  };
});

const unaryTestCalls = () => vi.mocked(feelin.unaryTest).mock.calls.length;
const evaluateCalls = () => vi.mocked(feelin.evaluate).mock.calls.length;

beforeEach(() => {
  vi.mocked(feelin.unaryTest).mockClear();
  vi.mocked(feelin.evaluate).mockClear();
});

describe('memoizedUnaryTest', () => {
  it('returns the same result as unaryTest', () => {
    expect(memoizedUnaryTest('a = "x" or b = null', { a: 'x' })).toBe(true);
    expect(memoizedUnaryTest('a = "x" or b = null', { a: 'y', b: 1 })).toBe(false);
  });

  it('does not evaluate again when only unreferenced fields change', () => {
    memoizedUnaryTest('k1 = true', { k1: true, other: 'a' });
    memoizedUnaryTest('k1 = true', { k1: true, other: 'ab' });
    memoizedUnaryTest('k1 = true', { k1: true, other: 'abc' });

    expect(unaryTestCalls()).toBe(1);
  });

  it('evaluates again when a referenced field changes', () => {
    expect(memoizedUnaryTest('k2 = true', { k2: true })).toBe(true);
    expect(memoizedUnaryTest('k2 = true', { k2: false })).toBe(false);

    expect(unaryTestCalls()).toBe(2);
  });

  it('tells an absent field from one that is present with undefined', () => {
    expect(memoizedUnaryTest('k3 = null', {})).toBe(feelin.unaryTest('k3 = null', {}));
    expect(memoizedUnaryTest('k3 = null', { k3: undefined })).toBe(
      feelin.unaryTest('k3 = null', { k3: undefined })
    );
    expect(memoizedUnaryTest('k3 = null', { k3: null })).toBe(true);
  });

  it('evaluates again when a nested value of a referenced object changes', () => {
    expect(memoizedUnaryTest('this.k4 = 1', { this: { k4: 1 } })).toBe(true);
    expect(memoizedUnaryTest('this.k4 = 1', { this: { k4: 2 } })).toBe(false);
  });

  it('always evaluates expressions with function calls', () => {
    memoizedUnaryTest('today() > k5', { k5: null });
    memoizedUnaryTest('today() > k5', { k5: null });

    expect(unaryTestCalls()).toBe(2);
  });

  it('throws like unaryTest on invalid expressions', () => {
    expect(() => memoizedUnaryTest('k6 +', { k6: 1 })).toThrow();
  });
});

describe('memoizedEvaluate', () => {
  it('evaluates again only when a referenced field changes', () => {
    expect(memoizedEvaluate('n1 * n2', { n1: 2, n2: 3, other: 'a' })).toBe(6);
    expect(memoizedEvaluate('n1 * n2', { n1: 2, n2: 3, other: 'b' })).toBe(6);
    expect(memoizedEvaluate('n1 * n2', { n1: 2, n2: 4, other: 'b' })).toBe(8);

    expect(evaluateCalls()).toBe(2);
  });
});
