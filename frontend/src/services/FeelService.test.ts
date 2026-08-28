// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  changeRequiredDefinitionForFieldsWithHideIfDefinition,
  collectHiddenPaths,
  dropErrorsOfHiddenFields,
  evaluateHideIfAndFeel,
} from './FeelService';
import type { RJSFSchema } from '@rjsf/utils';
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
