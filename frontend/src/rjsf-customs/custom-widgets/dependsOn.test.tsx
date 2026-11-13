// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { renderHook } from '@testing-library/react';
import { ObjectDataContext, getPropertyPath, useDependencyValues } from './dependsOn';

it.each([{}, { category: null }])(
  'an empty local field shadows a filled outer field: %j',
  formData => {
    const { result } = renderHook(
      () => useDependencyValues(['category'], { formData: { category: 'root' } }),
      {
        wrapper: ({ children }) => (
          <ObjectDataContext.Provider
            value={{ formData, schema: { properties: { category: {} } } }}>
            {children}
          </ObjectDataContext.Provider>
        ),
      }
    );
    expect(result.current).toEqual([null]);
  }
);

it('reads an enclosing row before the root when the local row does not define the field', () => {
  const { result } = renderHook(
    () =>
      useDependencyValues(['category', 'global'], { formData: { category: 'root', global: 0 } }),
    {
      wrapper: ({ children }) => (
        <ObjectDataContext.Provider
          value={{
            formData: {},
            schema: { properties: {} },
            parent: { formData: { category: 'parent' }, schema: { properties: { category: {} } } },
          }}>
          {children}
        </ObjectDataContext.Provider>
      ),
    }
  );
  expect(result.current).toEqual(['parent', 0]);
});

it('keeps underscores in names and includes every nested row index', () => {
  expect(
    getPropertyPath('root_vehicle_groups_2_vehicle_list_3_car_sub_type', [
      'vehicle_groups',
      'vehicle_list',
      'car_sub_type',
    ])
  ).toEqual(['vehicle_groups', 2, 'vehicle_list', 3, 'car_sub_type']);
});
