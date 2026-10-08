// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { computeColumnClasses } from '@/rjsf-customs/templates/layoutColumns';

describe('computeColumnClasses', () => {
  it('keeps equal widths when no field has explicit columns', () => {
    expect(computeColumnClasses([undefined])).toEqual(['col-md-12']);
    expect(computeColumnClasses([undefined, undefined])).toEqual(['col-lg-6', 'col-lg-6']);
    expect(computeColumnClasses([undefined, undefined, undefined])).toEqual([
      'col-lg-4',
      'col-lg-4',
      'col-lg-4',
    ]);
    expect(computeColumnClasses([undefined, undefined, undefined, undefined])).toEqual([
      'col-lg-3',
      'col-lg-3',
      'col-lg-3',
      'col-lg-3',
    ]);
  });

  it('converts 16th ratios to 12th ratios', () => {
    expect(computeColumnClasses([12, 4])).toEqual(['col-lg-9', 'col-lg-3']);
    expect(computeColumnClasses([3, 13])).toEqual(['col-lg-2', 'col-lg-10']);
    expect(computeColumnClasses([8, 8])).toEqual(['col-lg-6', 'col-lg-6']);
    expect(computeColumnClasses([4, 4, 4, 4])).toEqual([
      'col-lg-3',
      'col-lg-3',
      'col-lg-3',
      'col-lg-3',
    ]);
  });

  it('does not stretch fields that do not fill the row', () => {
    expect(computeColumnClasses([4])).toEqual(['col-lg-3']);
    expect(computeColumnClasses([8])).toEqual(['col-lg-6']);
    expect(computeColumnClasses([7, 7])).toEqual(['col-lg-5', 'col-lg-5']);
  });

  it('lets fields without columns share the remaining space', () => {
    expect(computeColumnClasses([4, undefined])).toEqual(['col-lg-3', 'col-lg-9']);
    expect(computeColumnClasses([undefined, 4, undefined])).toEqual([
      'col-lg-5',
      'col-lg-3',
      'col-lg-4',
    ]);
    expect(computeColumnClasses([5, 5, 4, undefined])).toEqual([
      'col-lg-4',
      'col-lg-4',
      'col-lg-3',
      'col-lg-1',
    ]);
  });

  it('falls back to equal widths when explicit columns leave no room for auto fields', () => {
    expect(computeColumnClasses([16, undefined])).toEqual(['col-lg-6', 'col-lg-6']);
  });

  it('never exceeds twelve columns per row', () => {
    const classes = computeColumnClasses([5, 5, 6]);
    const total = classes.reduce((sum, c) => sum + Number(c.replace('col-lg-', '')), 0);
    expect(total).toBe(12);
  });
});
