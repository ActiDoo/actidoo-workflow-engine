// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { skipMinItemsPopulation } from './arrayDefaults';

describe('skipMinItemsPopulation', () => {
  it('keeps pre-filling dynamic lists (arrays of objects)', () => {
    expect(
      skipMinItemsPopulation({
        type: 'array',
        minItems: 1,
        items: { type: 'object', properties: {} },
      })
    ).toBe(false);
  });

  it('skips arrays of scalars such as a required multi-select', () => {
    expect(
      skipMinItemsPopulation({ type: 'array', minItems: 1, items: { type: 'string', oneOf: [] } })
    ).toBe(true);
  });

  it('skips attachment lists', () => {
    expect(
      skipMinItemsPopulation({
        type: 'array',
        minItems: 1,
        items: { type: 'object', properties: { datauri: { type: 'string', format: 'data-url' } } },
      })
    ).toBe(true);
  });

  it('does not skip when the items schema is missing', () => {
    expect(skipMinItemsPopulation({ type: 'array', minItems: 1 })).toBe(false);
  });
});
