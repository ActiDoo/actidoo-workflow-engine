// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// One module on purpose: every detail rule about form visibility (hide-if / FEEL) and
// empty values lives here, next to its neighbours - see the matching backend module
// backend/actidoo_wfe/wf/tests/test_form_semantics.py.

import { unaryTest, InterpreterContext } from 'feelin';
import type { RJSFSchema } from '@rjsf/utils';

import {
  normalizeEmptyStringComparisons,
  changeRequiredDefinitionForFieldsWithHideIfDefinition,
  collectHiddenPaths,
  dropErrorsOfHiddenFields,
  evaluateHideIfAndFeel,
} from './FeelService';
import {
  buildEvaluationContext,
  buildMaskedParentContext,
  resolveHiddenFields,
  HideIfEvaluator,
} from './feelContext';
import { collectBlankRequiredPaths, isBlank } from './emptyValues';
import form010Fixture from '@/test/workflows/test-flow-dynamic-list-hidden/form010-fill.fixture.json';

describe('evaluateHideIfAndFeel', () => {
  it('hides a field whose hideif condition is met', () => {
    const uiSchema = { a: { 'ui:hideif': 'x = true' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: true }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBe('hidden');
  });

  it('keeps a field visible when the condition is not met', () => {
    const uiSchema = { a: { 'ui:hideif': 'x = true' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: false }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBeUndefined();
  });

  it('strips a leading = marker from the expression', () => {
    const uiSchema = { a: { 'ui:hideif': '=x = true' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: true }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBe('hidden');
  });

  it('treats invalid expressions as not hidden', () => {
    const uiSchema = { a: { 'ui:hideif': '((((' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: true }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBeUndefined();
  });

  it('unhides a field that a previous evaluation hid', () => {
    const uiSchema = { a: { 'ui:hideif': 'x = true', 'ui:widget': 'hidden' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: false }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBeUndefined();
  });

  it('defaults visible-but-missing booleans to false', () => {
    const uiSchema = { b: { 'ui:hideif': 'a = false' } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'boolean' }, b: { type: 'string' } },
    };

    const { newUiSchema } = evaluateHideIfAndFeel({}, uiSchema, schema);

    expect(newUiSchema?.b['ui:widget']).toBe('hidden');
  });

  it('cascades hiding through hidden boolean fields (fixpoint)', () => {
    const uiSchema = {
      a: { 'ui:hideif': 'x = true' },
      b: { 'ui:hideif': 'a = false' },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'boolean' }, b: { type: 'string' } },
    };

    const { newUiSchema } = evaluateHideIfAndFeel({ x: true, a: true }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBe('hidden');
    expect(newUiSchema?.b['ui:widget']).toBe('hidden');
  });

  it('restores ui:required into the schema for visible fields', () => {
    const uiSchema = { a: { 'ui:hideif': 'x = true', 'ui:required': true } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newSchema } = evaluateHideIfAndFeel({ x: false }, uiSchema, schema);

    expect(newSchema.required).toEqual(['a']);
  });

  it('does not mark hidden fields as required', () => {
    const uiSchema = { a: { 'ui:hideif': 'x = true', 'ui:required': true } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newSchema } = evaluateHideIfAndFeel({ x: true }, uiSchema, schema);

    expect(newSchema.required).toBeUndefined();
  });

  it('masks hidden fields inside this like the bare names', () => {
    // In a list row the row data is reachable both as bare name and as this.<name>; a
    // hidden field must read as null either way.
    const uiSchema = { a: { 'ui:hideif': '=x = true' }, b: { 'ui:hideif': '=this.a = null' } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' } },
    };
    const row = { x: true, a: 'stale value' };

    const { newUiSchema } = evaluateHideIfAndFeel({ ...row, this: row }, uiSchema, schema);

    expect(newUiSchema?.a['ui:widget']).toBe('hidden');
    expect(newUiSchema?.b['ui:widget']).toBe('hidden');
  });

  it('reads a blank or null field as null, as the server does', () => {
    const uiSchema = { b: { 'ui:hideif': '=a = null' }, c: { 'ui:hideif': '=this.a = null' } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' } },
    };

    for (const a of ['   ', null]) {
      const { newUiSchema } = evaluateHideIfAndFeel({ a, this: { a } }, uiSchema, schema);
      expect(newUiSchema?.b['ui:widget']).toBe('hidden');
      expect(newUiSchema?.c['ui:widget']).toBe('hidden');
    }
  });

  it('evaluates FEEL expressions in ui:description', () => {
    const uiSchema = { a: { 'ui:description': 'Summe: {{ numberA * numberB }} Euro' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({ numberA: 3, numberB: 2 }, uiSchema, schema);

    expect(newUiSchema?.a['ui:description']).toBe('Summe: 6,00 Euro');
  });

  it('replaces unevaluable description expressions with an empty string', () => {
    const uiSchema = { a: { 'ui:description': 'Summe: {{ missing * 2 }} Euro' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    const { newUiSchema } = evaluateHideIfAndFeel({}, uiSchema, schema);

    expect(newUiSchema?.a['ui:description']).toBe('Summe:  Euro');
  });

  it('returns inputs unchanged without a uiSchema', () => {
    const schema: RJSFSchema = { type: 'object', properties: {} };

    const result = evaluateHideIfAndFeel({ x: true }, undefined, schema);

    expect(result).toEqual({ newUiSchema: undefined, newSchema: schema, hide: false });
  });
});

describe('changeRequiredDefinitionForFieldsWithHideIfDefinition', () => {
  it('moves required to ui:required for fields with hideif', () => {
    const schema: any = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' } },
      required: ['a', 'b'],
    };
    const uiSchema: any = { a: { 'ui:hideif': 'x = true' } };

    changeRequiredDefinitionForFieldsWithHideIfDefinition(schema, uiSchema);

    expect(schema.required).toEqual(['b']);
    expect(uiSchema.a['ui:required']).toBe(true);
  });

  it('handles nested array item properties', () => {
    const schema: any = {
      type: 'object',
      properties: {
        list: {
          type: 'array',
          items: {
            type: 'object',
            properties: { inner: { type: 'string' } },
            required: ['inner'],
          },
        },
      },
    };
    const uiSchema: any = { list: { items: { inner: { 'ui:hideif': 'x = true' } } } };

    changeRequiredDefinitionForFieldsWithHideIfDefinition(schema, uiSchema);

    expect(schema.properties.list.items.required).toEqual([]);
    expect(uiSchema.list.items.inner['ui:required']).toBe(true);
  });

  it('leaves fields without hideif untouched', () => {
    const schema: any = {
      type: 'object',
      properties: { a: { type: 'string' } },
      required: ['a'],
    };
    const uiSchema: any = { a: {} };

    changeRequiredDefinitionForFieldsWithHideIfDefinition(schema, uiSchema);

    expect(schema.required).toEqual(['a']);
    expect(uiSchema.a['ui:required']).toBeUndefined();
  });
});

describe('normalizeEmptyStringComparisons', () => {
  // An empty field is null, never "" - see the matching backend conversion.
  it('reads comparisons against "" as comparisons against null', () => {
    const uiSchema = {
      note: { 'ui:hideif': '=comment = ""' },
      reminder: { 'ui:hideif': '=comment != ""' },
      reversed: { 'ui:hideif': '="" = comment' },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        comment: { type: 'string' },
        note: { type: 'string' },
        reminder: { type: 'string' },
        reversed: { type: 'string' },
      },
    };

    const unset = evaluateHideIfAndFeel({}, uiSchema, schema).newUiSchema;
    expect(unset?.note['ui:widget']).toBe('hidden');
    expect(unset?.reversed['ui:widget']).toBe('hidden');
    expect(unset?.reminder['ui:widget']).toBeUndefined();

    const set = evaluateHideIfAndFeel({ comment: 'x' }, uiSchema, schema).newUiSchema;
    expect(set?.note['ui:widget']).toBeUndefined();
    expect(set?.reminder['ui:widget']).toBe('hidden');
  });

  it('leaves other string literals alone', () => {
    expect(normalizeEmptyStringComparisons('x = "a" or y != ""')).toBe('x = "a" or y != null');
  });
});

describe('collectHiddenPaths', () => {
  const list = (properties: Record<string, any>, required?: string[]): any => ({
    type: 'array',
    items: { type: 'object', properties, ...(required ? { required } : {}) },
  });

  it('returns nothing without a uiSchema or schema', () => {
    expect(collectHiddenPaths(undefined, { type: 'object' }, { x: true })).toEqual([]);
    expect(collectHiddenPaths({ a: { 'ui:hideif': '=x = true' } }, undefined, { x: true })).toEqual(
      []
    );
  });

  it('lists a root field whose condition is met and keeps the others', () => {
    const uiSchema = { a: { 'ui:hideif': '=x = true' }, b: { 'ui:hideif': '=x = false' }, c: {} };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' } },
    };

    expect(collectHiddenPaths(uiSchema, schema, { x: true })).toEqual([['a']]);
  });

  it('ignores ui: keys and tolerates form data that is not an object', () => {
    const uiSchema = {
      'ui:layout': { row: ['a'] },
      'ui:field': 'layout',
      a: { 'ui:hideif': '=x = true' },
    };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    expect(collectHiddenPaths(uiSchema, schema, undefined)).toEqual([]);
    expect(collectHiddenPaths(uiSchema, schema, 'junk')).toEqual([]);
    expect(collectHiddenPaths(uiSchema, schema, { x: true })).toEqual([['a']]);
  });

  it('treats an invalid expression as visible', () => {
    const uiSchema = { a: { 'ui:hideif': '=((((' } };
    const schema: RJSFSchema = { type: 'object', properties: { a: { type: 'string' } } };

    expect(collectHiddenPaths(uiSchema, schema, { x: true })).toEqual([]);
  });

  it('cascades through hidden root fields like the rendering does', () => {
    // a disappears with x, and b depends on a being absent.
    const uiSchema = { a: { 'ui:hideif': '=x = true' }, b: { 'ui:hideif': '=a = null' } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' } },
    };

    expect(collectHiddenPaths(uiSchema, schema, { x: true, a: 'value' })).toEqual([['a'], ['b']]);
    expect(collectHiddenPaths(uiSchema, schema, { x: false, a: 'value' })).toEqual([]);
  });

  it('lists a hidden root list without descending into its rows', () => {
    const uiSchema = {
      mylist: { 'ui:hideif': '=x = true', items: { note: { 'ui:hideif': '=this.flag = true' } } },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { mylist: list({ flag: { type: 'boolean' }, note: { type: 'string' } }) },
    };
    const data = { x: true, mylist: [{ flag: true, note: 'n' }] };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([['mylist']]);
  });

  it('evaluates row fields per row against this.', () => {
    const uiSchema = { mylist: { items: { note: { 'ui:hideif': '=this.flag = true' } } } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { mylist: list({ flag: { type: 'boolean' }, note: { type: 'string' } }) },
    };
    const data = { mylist: [{ flag: true }, { flag: false }, { flag: true }] };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([
      ['mylist', 0, 'note'],
      ['mylist', 2, 'note'],
    ]);
  });

  it('lets row fields see root fields', () => {
    const uiSchema = { mylist: { items: { note: { 'ui:hideif': '=variant = "compact"' } } } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { variant: { type: 'string' }, mylist: list({ note: { type: 'string' } }) },
    };

    expect(collectHiddenPaths(uiSchema, schema, { variant: 'compact', mylist: [{}, {}] })).toEqual([
      ['mylist', 0, 'note'],
      ['mylist', 1, 'note'],
    ]);
    expect(collectHiddenPaths(uiSchema, schema, { variant: 'full', mylist: [{}, {}] })).toEqual([]);
  });

  it('masks hidden root fields in the row context', () => {
    // x still has its value in the data, but once y hides it, a row condition on that
    // value no longer matches - as when the row is rendered.
    const uiSchema = {
      x: { 'ui:hideif': '=y = true' },
      mylist: { items: { note: { 'ui:hideif': '=x = "v"' } } },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        x: { type: 'string' },
        y: { type: 'boolean' },
        mylist: list({ note: { type: 'string' } }),
      },
    };

    expect(collectHiddenPaths(uiSchema, schema, { x: 'v', y: false, mylist: [{}] })).toEqual([
      ['mylist', 0, 'note'],
    ]);
    expect(collectHiddenPaths(uiSchema, schema, { x: 'v', y: true, mylist: [{}] })).toEqual([
      ['x'],
    ]);
  });

  it('reads a hidden root field as null in the row context, as the backend does', () => {
    const uiSchema = {
      x: { 'ui:hideif': '=y = true' },
      mylist: { items: { note: { 'ui:hideif': '=x = null' } } },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        x: { type: 'string' },
        y: { type: 'boolean' },
        mylist: list({ note: { type: 'string' } }),
      },
    };

    // x hidden with a stale value: null for the row.
    expect(collectHiddenPaths(uiSchema, schema, { x: 'v', y: true, mylist: [{}] })).toEqual([
      ['x'],
      ['mylist', 0, 'note'],
    ]);
    // x shown with a value: not null.
    expect(collectHiddenPaths(uiSchema, schema, { x: 'v', y: false, mylist: [{}] })).toEqual([]);
    // x shown but empty: null as well.
    expect(collectHiddenPaths(uiSchema, schema, { y: false, mylist: [{}] })).toEqual([
      ['mylist', 0, 'note'],
    ]);
  });

  it('reads a hidden field of the same row as null through this.', () => {
    const uiSchema = {
      mylist: {
        items: {
          kind: { 'ui:hideif': '=hideKind = true' },
          note: { 'ui:hideif': '=this.kind = null or this.kind != "personal"' },
        },
      },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        hideKind: { type: 'boolean' },
        mylist: list({ kind: { type: 'string' }, note: { type: 'string' } }),
      },
    };
    const rows = { mylist: [{ kind: 'personal' }] };

    expect(collectHiddenPaths(uiSchema, schema, { hideKind: false, ...rows })).toEqual([]);
    expect(collectHiddenPaths(uiSchema, schema, { hideKind: true, ...rows })).toEqual([
      ['mylist', 0, 'kind'],
      ['mylist', 0, 'note'],
    ]);
  });

  it('defaults visible-but-missing booleans of a row to false like the root does', () => {
    const uiSchema = { mylist: { items: { note: { 'ui:hideif': '=flag = false' } } } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { mylist: list({ flag: { type: 'boolean' }, note: { type: 'string' } }) },
    };

    expect(collectHiddenPaths(uiSchema, schema, { mylist: [{}] })).toEqual([['mylist', 0, 'note']]);
  });

  it('cascades within a row', () => {
    const uiSchema = {
      mylist: {
        items: { a: { 'ui:hideif': '=this.flag = true' }, b: { 'ui:hideif': '=a = null' } },
      },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        mylist: list({ flag: { type: 'boolean' }, a: { type: 'string' }, b: { type: 'string' } }),
      },
    };

    expect(collectHiddenPaths(uiSchema, schema, { mylist: [{ flag: true, a: 'v' }] })).toEqual([
      ['mylist', 0, 'a'],
      ['mylist', 0, 'b'],
    ]);
  });

  it('lists a nested list hidden per row by a root field and stops there', () => {
    // The reported case: the inner list is hidden while the select says yes, and its
    // rows carry an empty required field that must not surface as a path of its own.
    const uiSchema = {
      outer: { items: { inner: { 'ui:hideif': '=choice = "yes"', items: { v: {} } } } },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        choice: { type: 'string' },
        outer: list({ inner: list({ v: { type: 'string' } }, ['v']) }),
      },
    };
    const data = { choice: 'yes', outer: [{ inner: [{}] }, { inner: [{}, {}] }] };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([
      ['outer', 0, 'inner'],
      ['outer', 1, 'inner'],
    ]);
    expect(collectHiddenPaths(uiSchema, schema, { ...data, choice: 'no' })).toEqual([]);
  });

  it('lets inner rows see their enclosing row as parent', () => {
    const uiSchema = {
      outer: { items: { inner: { items: { v: { 'ui:hideif': '=parent.kind = "a"' } } } } },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        outer: list({ kind: { type: 'string' }, inner: list({ v: { type: 'string' } }) }),
      },
    };
    const data = {
      outer: [
        { kind: 'a', inner: [{ v: 1 }, { v: 2 }] },
        { kind: 'b', inner: [{ v: 3 }] },
      ],
    };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([
      ['outer', 0, 'inner', 0, 'v'],
      ['outer', 0, 'inner', 1, 'v'],
    ]);
  });

  it('masks hidden fields of the enclosing row in the parent chain', () => {
    // kind keeps its value in the data, but once hideKind hides it, the inner row no
    // longer sees it through parent.
    const uiSchema = {
      outer: {
        items: {
          kind: { 'ui:hideif': '=hideKind = true' },
          inner: { items: { v: { 'ui:hideif': '=parent.kind = "a"' } } },
        },
      },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        hideKind: { type: 'boolean' },
        outer: list({ kind: { type: 'string' }, inner: list({ v: { type: 'string' } }) }),
      },
    };
    const data = { hideKind: false, outer: [{ kind: 'a', inner: [{}] }] };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([['outer', 0, 'inner', 0, 'v']]);
    expect(collectHiddenPaths(uiSchema, schema, { ...data, hideKind: true })).toEqual([
      ['outer', 0, 'kind'],
    ]);
  });

  it('reads a hidden field of the enclosing row as null through parent.', () => {
    const uiSchema = {
      outer: {
        items: {
          kind: { 'ui:hideif': '=hideKind = true' },
          inner: { items: { v: { 'ui:hideif': '=parent.kind = null' } } },
        },
      },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        hideKind: { type: 'boolean' },
        outer: list({ kind: { type: 'string' }, inner: list({ v: { type: 'string' } }) }),
      },
    };
    const data = { hideKind: true, outer: [{ kind: 'a', inner: [{}] }] };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([
      ['outer', 0, 'kind'],
      ['outer', 0, 'inner', 0, 'v'],
    ]);
    expect(collectHiddenPaths(uiSchema, schema, { ...data, hideKind: false })).toEqual([]);
  });

  it('walks three levels and resolves parent.parent', () => {
    const uiSchema = {
      l1: {
        items: {
          l2: { items: { l3: { items: { v: { 'ui:hideif': '=parent.parent.top = "x"' } } } } },
        },
      },
    };
    const schema: RJSFSchema = {
      type: 'object',
      properties: {
        l1: list({ top: { type: 'string' }, l2: list({ l3: list({ v: { type: 'string' } }) }) }),
      },
    };
    const data = {
      l1: [
        { top: 'x', l2: [{ l3: [{}, {}] }] },
        { top: 'y', l2: [{ l3: [{}] }] },
      ],
    };

    expect(collectHiddenPaths(uiSchema, schema, data)).toEqual([
      ['l1', 0, 'l2', 0, 'l3', 0, 'v'],
      ['l1', 0, 'l2', 0, 'l3', 1, 'v'],
    ]);
  });

  it('skips rows that are not objects and lists that are not arrays', () => {
    const uiSchema = { mylist: { items: { note: { 'ui:hideif': '=this.flag = true' } } } };
    const schema: RJSFSchema = {
      type: 'object',
      properties: { mylist: list({ flag: { type: 'boolean' }, note: { type: 'string' } }) },
    };

    expect(
      collectHiddenPaths(uiSchema, schema, { mylist: [null, 'row', 5, [1], { flag: true }] })
    ).toEqual([['mylist', 4, 'note']]);
    expect(collectHiddenPaths(uiSchema, schema, { mylist: 'oops' })).toEqual([]);
    expect(collectHiddenPaths(uiSchema, schema, {})).toEqual([]);
  });

  it('resolves the generated schema of TestFlow_DynamicListHidden', () => {
    const { jsonschema, uischema } = form010Fixture as { jsonschema: RJSFSchema; uischema: any };
    const rows = { outer_list: [{ inner_list: [{}] }], other_list: [{}] };

    expect(collectHiddenPaths(uischema, jsonschema, { create_set: 'yes', ...rows })).toEqual([
      ['outer_list', 0, 'inner_list'],
    ]);
    expect(collectHiddenPaths(uischema, jsonschema, { create_set: 'no', ...rows })).toEqual([
      ['other_list'],
    ]);
    expect(collectHiddenPaths(uischema, jsonschema, rows)).toEqual([
      ['outer_list'],
      ['other_list'],
    ]);
  });
});

describe('dropErrorsOfHiddenFields', () => {
  const error = (property: string | undefined): { property?: string; message: string } => ({
    property,
    message: 'error',
  });

  it('returns the errors untouched when nothing is hidden', () => {
    const errors = [error('.a'), error('b')];

    expect(dropErrorsOfHiddenFields(errors, [])).toBe(errors);
  });

  it('drops an error on the hidden field itself', () => {
    expect(dropErrorsOfHiddenFields([error('.mylist'), error('.other')], [['mylist']])).toEqual([
      error('.other'),
    ]);
  });

  it('drops errors below a hidden path and keeps those of other rows', () => {
    const errors = [
      error('.outer.0.inner.0.v'),
      error('.outer.0.inner'),
      error('.outer.1.inner.0.v'),
      error('.outer.0.text'),
    ];

    expect(dropErrorsOfHiddenFields(errors, [['outer', 0, 'inner']])).toEqual([
      error('.outer.1.inner.0.v'),
      error('.outer.0.text'),
    ]);
  });

  it('understands the dot-less property of a required error on the root level', () => {
    const errors = [error('name'), error('other')];

    expect(dropErrorsOfHiddenFields(errors, [['name']])).toEqual([error('other')]);
  });

  it('matches whole segments only', () => {
    const errors = [error('.ab'), error('.a_b'), error('.a.b'), error('.mylist.10.v')];

    expect(dropErrorsOfHiddenFields(errors, [['a'], ['mylist', 1]])).toEqual([
      error('.ab'),
      error('.a_b'),
      error('.mylist.10.v'),
    ]);
  });

  it('keeps errors without a property', () => {
    const errors = [error(undefined), error('')];

    expect(dropErrorsOfHiddenFields(errors, [['a']])).toEqual(errors);
  });
});

// ----------------------------------------------------------------------------
// FEEL context helpers (feelContext.ts)

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

// ----------------------------------------------------------------------------
// Empty values (emptyValues.ts)

describe('isBlank', () => {
  it('treats nothing, null and whitespace-only strings as blank', () => {
    expect(isBlank(undefined)).toBe(true);
    expect(isBlank(null)).toBe(true);
    expect(isBlank('')).toBe(true);
    expect(isBlank('   ')).toBe(true);
    expect(isBlank('\n\t')).toBe(true);
  });

  it('treats every other value as a value', () => {
    expect(isBlank('a')).toBe(false);
    expect(isBlank(' a ')).toBe(false);
    expect(isBlank(false)).toBe(false);
    expect(isBlank(0)).toBe(false);
    expect(isBlank([])).toBe(false);
    expect(isBlank({})).toBe(false);
  });
});

describe('collectBlankRequiredPaths', () => {
  const schema: RJSFSchema = {
    type: 'object',
    required: ['name', 'choice'],
    properties: {
      name: { type: 'string' },
      choice: { type: ['string', 'null'] },
      note: { type: 'string' },
      rows: {
        type: 'array',
        items: { type: 'object', required: ['label'], properties: { label: { type: 'string' } } },
      },
    },
  };

  it('reports required fields that are present but blank', () => {
    expect(collectBlankRequiredPaths(schema, {}, { name: '   ', choice: null }, [])).toEqual([
      ['name'],
      ['choice'],
    ]);
  });

  it('leaves absent required fields to the schema validation', () => {
    expect(collectBlankRequiredPaths(schema, {}, {}, [])).toEqual([]);
  });

  it('ignores keys that are present as undefined - rjsf hands the data over that way', () => {
    expect(collectBlankRequiredPaths(schema, {}, { name: undefined, choice: 'a' }, [])).toEqual([]);
  });

  it('leaves object-typed (attachment) fields to the schema validation', () => {
    const withFile: RJSFSchema = {
      type: 'object',
      required: ['file'],
      properties: { file: { type: 'object', properties: { datauri: { type: 'string' } } } },
    };

    expect(collectBlankRequiredPaths(withFile, {}, { file: null }, [])).toEqual([]);
  });

  it('ignores blank optional fields and filled required ones', () => {
    expect(
      collectBlankRequiredPaths(schema, {}, { name: 'x', choice: 'a', note: ' ' }, [])
    ).toEqual([]);
  });

  it('walks list rows', () => {
    const data = { name: 'x', choice: 'a', rows: [{ label: 'ok' }, { label: ' ' }, {}] };

    expect(collectBlankRequiredPaths(schema, {}, data, [])).toEqual([['rows', 1, 'label']]);
  });

  it('skips fields on or below a hidden path', () => {
    const data = { name: ' ', choice: 'a', rows: [{ label: ' ' }] };

    expect(collectBlankRequiredPaths(schema, {}, data, [['rows']])).toEqual([['name']]);
    expect(collectBlankRequiredPaths(schema, {}, data, [['name'], ['rows', 0, 'label']])).toEqual(
      []
    );
  });

  it('tolerates data that is not an object', () => {
    expect(collectBlankRequiredPaths(schema, {}, undefined, [])).toEqual([]);
    expect(collectBlankRequiredPaths(schema, {}, 'junk', [])).toEqual([]);
  });
});
