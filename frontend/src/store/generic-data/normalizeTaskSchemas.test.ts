// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { normalizeTaskSchemasForResponse } from './normalizeTaskSchemas';
import {
  normalizeArrayDefaultsInJsonSchema,
  normalizeItemgroupCopyableInUiSchema,
} from './schemaNormalization';
import { WeDataKey } from './setup';

describe('normalizeArrayDefaultsInJsonSchema', () => {
  it('injects default [] into array schemas without a default', () => {
    const schema: any = { type: 'array', items: { type: 'string' } };

    normalizeArrayDefaultsInJsonSchema(schema);

    expect(schema.default).toEqual([]);
  });

  it('keeps an existing default untouched', () => {
    const schema: any = { type: 'array', items: { type: 'string' }, default: ['x'] };

    normalizeArrayDefaultsInJsonSchema(schema);

    expect(schema.default).toEqual(['x']);
  });

  it('walks nested properties and items', () => {
    const schema: any = {
      type: 'object',
      properties: {
        outer: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              inner: { type: 'array', items: { type: 'string' } },
            },
          },
        },
      },
    };

    normalizeArrayDefaultsInJsonSchema(schema);

    expect(schema.properties.outer.default).toEqual([]);
    expect(schema.properties.outer.items.properties.inner.default).toEqual([]);
  });

  it('recognizes type arrays containing array', () => {
    const schema: any = { type: ['array', 'null'], items: { type: 'string' } };

    normalizeArrayDefaultsInJsonSchema(schema);

    expect(schema.default).toEqual([]);
  });

  it('ignores non-object input', () => {
    expect(() => normalizeArrayDefaultsInJsonSchema(null)).not.toThrow();
    expect(() => normalizeArrayDefaultsInJsonSchema('x')).not.toThrow();
  });
});

describe('normalizeItemgroupCopyableInUiSchema', () => {
  it('marks itemgroups as copyable', () => {
    const uischema: any = { group: { 'ui:arrayAddButtonText': 'Add row' } };

    normalizeItemgroupCopyableInUiSchema(uischema);

    expect(uischema.group['ui:copyable']).toBe(true);
  });

  it('respects an explicit ui:copyable value', () => {
    const uischema: any = {
      group: { 'ui:arrayAddButtonText': 'Add row', 'ui:copyable': false },
    };

    normalizeItemgroupCopyableInUiSchema(uischema);

    expect(uischema.group['ui:copyable']).toBe(false);
  });

  it('does not touch plain fields', () => {
    const uischema: any = { field: { 'ui:widget': 'text' } };

    normalizeItemgroupCopyableInUiSchema(uischema);

    expect(uischema.field['ui:copyable']).toBeUndefined();
  });
});

describe('normalizeTaskSchemasForResponse', () => {
  const task = (): any => ({
    id: 't1',
    jsonschema: {
      type: 'object',
      properties: { list: { type: 'array', items: { type: 'string' } } },
    },
    uischema: { list: { 'ui:arrayAddButtonText': 'Add' } },
  });

  it('normalizes all task schemas of a user tasks response', () => {
    const data = { usertasks: [task()] };

    const result = normalizeTaskSchemasForResponse(WeDataKey.MY_USER_TASKS, data);

    expect(result.usertasks[0].jsonschema.properties.list.default).toEqual([]);
    expect(result.usertasks[0].uischema.list['ui:copyable']).toBe(true);
  });

  it('does not mutate the original response', () => {
    const data = { usertasks: [task()] };

    normalizeTaskSchemasForResponse(WeDataKey.MY_USER_TASKS, data);

    expect(data.usertasks[0].jsonschema.properties.list.default).toBeUndefined();
    expect(data.usertasks[0].uischema.list['ui:copyable']).toBeUndefined();
  });

  it('normalizes the task of a start workflow preview response', () => {
    const data = { task: task() };

    const result = normalizeTaskSchemasForResponse(WeDataKey.START_WORKFLOW_PREVIEW, data);

    expect(result.task.jsonschema.properties.list.default).toEqual([]);
  });

  it('passes through unexpected shapes and other keys unchanged', () => {
    const malformed = { usertasks: 'nope' };

    expect(normalizeTaskSchemasForResponse(WeDataKey.MY_USER_TASKS, malformed)).toBe(malformed);
    expect(normalizeTaskSchemasForResponse(WeDataKey.WORKFLOWS, { any: 1 })).toEqual({ any: 1 });
    expect(normalizeTaskSchemasForResponse(WeDataKey.MY_USER_TASKS, null)).toBe(null);
  });

  it('leaves tasks without schemas unchanged', () => {
    const bareTask = { id: 't2' };
    const data = { usertasks: [bareTask] };

    const result = normalizeTaskSchemasForResponse(WeDataKey.MY_USER_TASKS, data);

    expect(result.usertasks[0]).toBe(bareTask);
  });
});
