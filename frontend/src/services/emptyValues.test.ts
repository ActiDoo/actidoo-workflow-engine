// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { RJSFSchema } from '@rjsf/utils';

import { collectBlankRequiredPaths, isBlank } from './emptyValues';

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
