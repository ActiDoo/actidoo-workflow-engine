// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { computeColumnClasses } from '@/rjsf-customs/templates/layoutColumns';

describe('computeColumnClasses', () => {
  it('gives a field with columns exactly that many sixteenths', () => {
    expect(computeColumnClasses([2, 2, 2, 2])).toEqual([
      'pc-col-2',
      'pc-col-2',
      'pc-col-2',
      'pc-col-2',
    ]);
    expect(computeColumnClasses([12, 4])).toEqual(['pc-col-12', 'pc-col-4']);
    expect(computeColumnClasses([3, 13])).toEqual(['pc-col-3', 'pc-col-13']);
  });

  it('does not stretch fields that do not fill the row', () => {
    expect(computeColumnClasses([4])).toEqual(['pc-col-4']);
    expect(computeColumnClasses([7, 7])).toEqual(['pc-col-7', 'pc-col-7']);
  });

  it('lets fields without columns share the rest of the row', () => {
    expect(computeColumnClasses([undefined])).toEqual(['pc-col']);
    expect(computeColumnClasses([undefined, undefined, undefined, undefined])).toEqual([
      'pc-col',
      'pc-col',
      'pc-col',
      'pc-col',
    ]);
    expect(computeColumnClasses([undefined, 4, undefined])).toEqual([
      'pc-col',
      'pc-col-4',
      'pc-col',
    ]);
    expect(computeColumnClasses([5, 5, 4, undefined])).toEqual([
      'pc-col-5',
      'pc-col-5',
      'pc-col-4',
      'pc-col',
    ]);
  });

  it('caps a width at the full row', () => {
    expect(computeColumnClasses([20])).toEqual(['pc-col-16']);
  });
});
