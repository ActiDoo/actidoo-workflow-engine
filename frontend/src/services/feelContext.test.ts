// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { unaryTest, InterpreterContext } from 'feelin';
import {
  buildEvaluationContext,
  buildMaskedParentContext,
  resolveHiddenFields,
  HideIfEvaluator,
} from './feelContext';

const evaluateHideIf: HideIfEvaluator = (expression, context) => {
  try {
    return unaryTest(expression, { ...(context ?? {}) });
  } catch {
    return false;
  }
};

describe('resolveHiddenFields', () => {
  it('collects fields whose hideif matches and masks them in the context', () => {
    const uiSchema: any = { secret: { 'ui:hideif': '=x = true' } };
    const data = { x: true, secret: 'value' };

    const { hiddenFields, maskedContext } = resolveHiddenFields(uiSchema, data, evaluateHideIf);

    expect(hiddenFields).toEqual(new Set(['secret']));
    expect(maskedContext).toEqual({ x: true });
    expect(maskedContext).not.toHaveProperty('secret');
  });

  it('removes hidden fields, so a comparison with null matches them', () => {
    // A key left in place with undefined would not: FEEL only reads an absent name as null.
    const uiSchema: any = {
      a: { 'ui:hideif': '=x = true' },
      b: { 'ui:hideif': '=a = null' },
    };
    const data = { x: true, a: 'stale value', b: 1 };

    const { hiddenFields, maskedContext } = resolveHiddenFields(uiSchema, data, evaluateHideIf);

    expect(hiddenFields).toEqual(new Set(['a', 'b']));
    expect(maskedContext).toEqual({ x: true });
  });

  it('keeps fields visible when the condition does not match', () => {
    const uiSchema: any = { secret: { 'ui:hideif': '=x = true' } };

    const { hiddenFields, maskedContext } = resolveHiddenFields(
      uiSchema,
      { x: false, secret: 'value' },
      evaluateHideIf
    );

    expect(hiddenFields.size).toBe(0);
    expect(maskedContext?.secret).toBe('value');
  });

  it('evaluates dependent hide-ifs against the masked value of hidden fields', () => {
    const uiSchema: any = {
      a: { 'ui:hideif': '=x = true' },
      b: { 'ui:hideif': '=a = 5' },
    };
    const data = { x: true, a: 5, b: 1 };

    const { hiddenFields, maskedContext } = resolveHiddenFields(uiSchema, data, evaluateHideIf);

    expect(hiddenFields).toEqual(new Set(['a']));
    expect(maskedContext).toEqual({ x: true, b: 1 });
  });

  it('mirrors masked fields into the this context', () => {
    const uiSchema: any = { secret: { 'ui:hideif': '=x = true' } };
    const data: InterpreterContext = {
      x: true,
      secret: 'value',
      this: { x: true, secret: 'value' },
    };

    const { maskedContext } = resolveHiddenFields(uiSchema, data, evaluateHideIf);

    expect(maskedContext?.this).toEqual({ x: true });
    expect(maskedContext?.this).not.toHaveProperty('secret');
  });

  it('returns the context unchanged without a uiSchema', () => {
    const data = { x: 1 };

    const { hiddenFields, maskedContext } = resolveHiddenFields(undefined, data, evaluateHideIf);

    expect(hiddenFields.size).toBe(0);
    expect(maskedContext).toBe(data);
  });
});

describe('buildEvaluationContext', () => {
  it('merges root context, item data and parent chain', () => {
    const root = { rootValue: 1 };
    const item = { itemValue: 2 };
    const parent = { parentValue: 3 };

    const ctx = buildEvaluationContext(root, item, parent);

    expect(ctx.rootValue).toBe(1);
    expect(ctx.itemValue).toBe(2);
    expect(ctx.parent).toBe(parent);
    expect(ctx.this).toEqual({ itemValue: 2, parent });
  });

  it('passes non-object item data through as this', () => {
    const ctx = buildEvaluationContext({ rootValue: 1 }, 'plain', undefined);

    expect(ctx.this).toBe('plain');
  });
});

describe('buildMaskedParentContext', () => {
  const rootData = {
    hideMe: true,
    listA: [
      {
        hideMe: true,
        secret: 'inner-secret',
        keep: 'kept',
        listB: [{ b: 2 }],
      },
    ],
  };
  const rootUiSchema: any = {
    listA: {
      items: {
        secret: { 'ui:hideif': '=hideMe = true' },
        listB: { items: {} },
      },
    },
  };

  it('returns the masked root context for top-level ids', () => {
    const masked = { hideMe: true, listA: rootData.listA };

    const result = buildMaskedParentContext(
      rootData,
      rootUiSchema,
      'root_listA_0',
      masked,
      evaluateHideIf
    );

    expect(result).toBe(masked);
  });

  it('masks hidden fields of each parent level for nested list items', () => {
    const result = buildMaskedParentContext(
      rootData,
      rootUiSchema,
      'root_listA_0_listB_0',
      rootData,
      evaluateHideIf
    );

    expect(result?.secret).toBeUndefined();
    expect(result?.keep).toBe('kept');
    expect((result?.parent as InterpreterContext)?.listA).toBe(rootData.listA);
  });

  it('falls back to the plain parent chain when schema and data do not align', () => {
    const result = buildMaskedParentContext(
      rootData,
      { otherList: { items: {} } } as any,
      'root_listA_0_listB_0',
      rootData,
      evaluateHideIf
    );

    expect(result?.keep).toBe('kept');
    expect(result?.secret).toBe('inner-secret');
  });

  it('returns the root context for ids without list segments', () => {
    const result = buildMaskedParentContext(
      rootData,
      rootUiSchema,
      'root_someField',
      rootData,
      evaluateHideIf
    );

    expect(result).toBe(rootData);
  });
});
