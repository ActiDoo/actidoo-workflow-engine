// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlow_DependsOn — see ../README.md.
//
// CAR Sub Type declares depends_on=car_type. The pair sits at the top level and inside the
// dynamic list "vehicles", where the dependency is the row's own CAR type.

import _ from 'lodash';
import { page, userEvent } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import form010 from './form010-fill.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const optionRequests: any[] = [];

beforeEach(() => {
  optionRequests.length = 0;
});

useFakeBackend(({ url, body }) => {
  const request = body as any;
  if (url.endsWith('user/strip_hidden_fields')) {
    return { data: { form_data: request.form_data } };
  }
  if (url.endsWith('user/search_property_options')) {
    optionRequests.push(request);
    const scope =
      request.property_path.length === 1
        ? request.form_data
        : _.get(request.form_data, request.property_path.slice(0, -1));
    const options =
      scope?.car_type === 'car'
        ? [
            { value: 'sedan', label: 'Sedan' },
            { value: 'shared', label: 'Standard car' },
          ]
        : scope?.car_type === 'truck'
        ? [
            { value: 'pickup', label: 'Pickup' },
            { value: 'shared', label: 'Standard truck' },
          ]
        : [];
    return { data: { options } };
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
    expect(payload.car_sub_type).toBeNull();
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
    expect(row.car_sub_type).toBeNull();
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

it('shows and copies row-specific labels even when both rows select the same ID', async () => {
  const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
  const { selectOption, addListRow } = renderTaskForm(form010);
  await selectOption('vehicles_0_car_type', 'Car');
  await selectOption('vehicles_0_car_sub_type', 'Standard car');
  await addListRow('Vehicles');
  await selectOption('vehicles_1_car_type', 'Truck');
  await selectOption('vehicles_1_car_sub_type', 'Standard truck');
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await expect.element(page.getByText('Standard car (ID: shared)', { exact: true })).toBeVisible();
  await expect
    .element(page.getByText('Standard truck (ID: shared)', { exact: true }))
    .toBeVisible();
  await page.getByRole('button', { name: 'Copy column' }).last().click();
  await expect
    .poll(() => writeText.mock.calls)
    .toEqual([['Standard car (ID: shared)\r\nStandard truck (ID: shared)']]);
  expect(
    optionRequests
      .filter(request => request.property_path[0] === 'vehicles')
      .every(request => typeof request.property_path[1] === 'number')
  ).toBe(true);
});

it('clears a multi-select to an empty array when its own dependency changes', async () => {
  const fixture = _.cloneDeep(form010);
  _.set(fixture, 'jsonschema.properties.vehicles.items.properties.car_sub_type', {
    type: 'array',
    title: 'CAR Sub Type',
    items: { type: 'string' },
  });
  _.set(
    fixture,
    ['uischema', 'vehicles', 'items', 'car_sub_type', 'ui:widget'],
    'MultiSelectDynamic'
  );
  const { selectOption, submitted, submit } = renderTaskForm(fixture);
  await selectOption('vehicles_0_car_type', 'Car');
  await selectOption('vehicles_0_car_sub_type', 'Sedan');
  await userEvent.keyboard('{Escape}');
  await selectOption('vehicles_0_car_type', 'Truck');
  await submit();
  expect(submitted.mock.calls[0][0].vehicles[0].car_sub_type).toEqual([]);
});

it('resolves nested list labels when opening the outer list overview', async () => {
  const fixture = _.cloneDeep(form010) as any;
  fixture.jsonschema.properties.groups = {
    type: 'array',
    title: 'Groups',
    items: {
      type: 'object',
      properties: { vehicles: fixture.jsonschema.properties.vehicles },
    },
  };
  fixture.uischema.groups = {
    'ui:label': 'Groups',
    'ui:defaultRepetitions': 1,
    'ui:arrayAllowAddRemove': 'True',
    items: {
      'ui:field': 'layout',
      'ui:layout': { vehicles: ['vehicles'] },
      vehicles: fixture.uischema.vehicles,
    },
  };
  for (const key of ['car_type', 'car_sub_type']) {
    fixture.uischema.groups.items.vehicles.items[key]['ui:path'] = ['groups', 'vehicles', key];
  }
  delete fixture.jsonschema.properties.vehicles;
  delete fixture.uischema.vehicles;
  fixture.uischema['ui:layout'].vehicles = ['groups'];
  const { selectOption } = renderTaskForm(fixture);
  await selectOption('groups_0_vehicles_0_car_type', 'Truck');
  await selectOption('groups_0_vehicles_0_car_sub_type', 'Pickup');
  await page.getByRole('button', { name: 'Overview', exact: true }).last().click();
  await expect.element(page.getByText('Pickup (ID: pickup)', { exact: true })).toBeVisible();
  expect(optionRequests.map(request => request.property_path)).toContainEqual([
    'groups',
    0,
    'vehicles',
    0,
    'car_sub_type',
  ]);
});

it('keeps prefilled selections when the form mounts with existing or template data', async () => {
  const initialData = {
    car_type: 'car',
    car_sub_type: 'sedan',
    vehicles: [{ car_type: 'truck', car_sub_type: 'pickup' }],
  };
  const { submitted, submit } = renderTaskForm(form010, initialData);
  await expect.element(page.getByText('Sedan', { exact: true })).toBeVisible();
  await expect.element(page.getByText('Pickup', { exact: true })).toBeVisible();
  await submit();
  expect(submitted.mock.calls[0][0]).toMatchObject(initialData);
});

it.each(['ui:disabled', 'ui:readonly'])(
  'keeps a %s selection when its dependency changes',
  async setting => {
    const fixture = _.cloneDeep(form010);
    _.set(fixture, ['uischema', 'car_sub_type', setting], true);
    const { selectOption, submitted, submit } = renderTaskForm(fixture, {
      car_type: 'car',
      car_sub_type: 'sedan',
    });
    await expect.element(page.getByText('Sedan', { exact: true })).toBeVisible();
    await selectOption('car_type', 'Truck');
    await submit();
    expect(submitted.mock.calls[0][0].car_sub_type).toBe('sedan');
    await expect.element(page.getByText('Sedan', { exact: true })).toBeVisible();
  }
);
