// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { computeGridTemplate } from '@/rjsf-customs/templates/layoutColumns';

const template = (...columns: Array<number | undefined>) => computeGridTemplate(columns);

describe('computeGridTemplate', () => {
  it('gives a field with columns exactly that many sixteenths', () => {
    expect(template(12, 4)).toBe('minmax(0, 12fr) minmax(0, 4fr)');
    expect(template(3, 13)).toBe('minmax(0, 3fr) minmax(0, 13fr)');
  });

  it('keeps the rest of the row free when the fields do not fill it', () => {
    expect(template(2, 2, 2, 2)).toBe(
      'minmax(0, 2fr) minmax(0, 2fr) minmax(0, 2fr) minmax(0, 2fr) minmax(0, 8fr)'
    );
    expect(template(4)).toBe('minmax(0, 4fr) minmax(0, 12fr)');
  });

  it('lets fields without columns share the rest of the row', () => {
    expect(template(undefined)).toBe('minmax(0, 16fr)');
    expect(template(undefined, undefined, undefined, undefined)).toBe(
      'minmax(0, 4fr) minmax(0, 4fr) minmax(0, 4fr) minmax(0, 4fr)'
    );
    expect(template(undefined, 4, undefined)).toBe('minmax(0, 6fr) minmax(0, 4fr) minmax(0, 6fr)');
    expect(template(5, 5, 4, undefined)).toBe(
      'minmax(0, 5fr) minmax(0, 5fr) minmax(0, 4fr) minmax(0, 2fr)'
    );
    const third = `minmax(0, ${16 / 3}fr)`;
    expect(template(undefined, undefined, undefined)).toBe(`${third} ${third} ${third}`);
  });

  it('shrinks widths that add up to more than 16 in proportion', () => {
    expect(template(12, 8)).toBe('minmax(0, 12fr) minmax(0, 8fr)');
  });
});
