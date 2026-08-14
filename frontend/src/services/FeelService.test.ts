// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  changeRequiredDefinitionForFieldsWithHideIfDefinition,
  evaluateHideIfAndFeel,
} from './FeelService';
import type { RJSFSchema } from '@rjsf/utils';

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
