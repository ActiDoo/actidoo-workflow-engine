// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlow_DependsOn — see ../README.md.
//
// CAR Sub Type declares depends_on=car_type. The pair sits at the top level and inside the
// dynamic list "vehicles", where the dependency is the row's own CAR type.

import { page } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import form010 from './form010-fill.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const optionRequests: any[] = [];

useFakeBackend(({ url, body }) => {
  if (url.endsWith('user/search_property_options')) {
    optionRequests.push(body);
    return {
      data: {
        options: [
          { value: 'sedan', label: 'Sedan' },
          { value: 'pickup', label: 'Pickup' },
        ],
      },
    };
  }
  throw new Error(`Unexpected request in test: ${url}`);
});

describe('Test Flow Depends On — Form010', () => {
  it('clears the top-level sub type when the car type changes', async () => {
    const { submitted, selectOption, submit } = renderTaskForm(form010);

    await selectOption('car_type', 'Car');
    await selectOption('car_sub_type', 'Sedan');
    await selectOption('car_type', 'Truck');
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    const payload = submitted.mock.calls[0][0];
    expect(payload.car_type).toBe('truck');
    expect(payload.car_sub_type || null).toBeNull();
  });

  it("clears the sub type of a list row only when the row's own car type changes", async () => {
    const { submitted, selectOption, submit } = renderTaskForm(form010);

    await selectOption('vehicles_0_car_type', 'Car');
    await selectOption('vehicles_0_car_sub_type', 'Sedan');
    await selectOption('car_type', 'Truck');
    await submit();
    await selectOption('vehicles_0_car_type', 'Truck');
    await submit();

    expect(submitted).toHaveBeenCalledTimes(2);
    expect(submitted.mock.calls[0][0].vehicles[0]).toMatchObject({
      car_type: 'car',
      car_sub_type: 'sedan',
    });
    const row = submitted.mock.calls[1][0].vehicles[0];
    expect(row.car_type).toBe('truck');
    expect(row.car_sub_type || null).toBeNull();
    expect(optionRequests.map(request => request.property_path)).toContainEqual([
      'vehicles',
      0,
      'car_sub_type',
    ]);
  });

  it('keeps the sub type of the next row when the row above is removed', async () => {
    const { submitted, field, selectOption, addListRow, submit } = renderTaskForm(form010);

    await expect.element(field('vehicles_0_car_type')).toBeInTheDocument();
    await addListRow('Vehicles');
    await selectOption('vehicles_1_car_type', 'Truck');
    await selectOption('vehicles_1_car_sub_type', 'Pickup');
    await page.getByRole('button', { name: 'Delete', exact: true }).first().click();
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    expect(submitted.mock.calls[0][0].vehicles).toEqual([
      { car_type: 'truck', car_sub_type: 'pickup' },
    ]);
  });
});
