// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlowDemoChangeFunction — see ../README.md.
//
// Company and the Product of each "gifts" row declare a change_function; the disabled
// Price of a row is derived from both on the server.

import _ from 'lodash';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import enterGifts from '@/test/workflows/test-flow-demo-change-function/enter-gifts.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const PRICES: Record<string, number> = { pen: 2, mug: 10 };
const price = (product: string, company: string): number | null =>
  product in PRICES ? PRICES[product] * (company === 'subsidiary' ? 1.5 : 1) : null;

const changeRequests: any[] = [];

beforeEach(() => {
  changeRequests.length = 0;
});

useFakeBackend(({ url, body }) => {
  const request = body as any;
  if (url.endsWith('user/strip_hidden_fields')) {
    return { data: { form_data: request.form_data } };
  }
  if (url.endsWith('user/form_change')) {
    changeRequests.push(request);
    const data = request.form_data;
    const rows: number[] =
      request.property_path.length === 1
        ? _.range((data.gifts ?? []).length)
        : [request.property_path[1]];
    const changes = rows
      .map(index => ({
        path: ['gifts', index, 'price'],
        value: price(data.gifts[index].product, data.company),
      }))
      .filter(change => change.value !== (_.get(data, change.path) ?? null));
    return { data: { changes } };
  }
  throw new Error(`Unexpected request in test: ${url}`);
});

const twoRows = () => ({
  gifts: [{ _row_id: 'a' }, { _row_id: 'b' }],
});

describe('Test Flow Demo Change Function — EnterGifts', () => {
  it('derives the price of the row whose product changed', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(enterGifts, twoRows());

    await selectOption('gifts_1_product', 'Mug');
    await expect.element(field('gifts_1_price')).toHaveValue(10);
    await submit();

    expect(changeRequests.map(request => request.property_path)).toEqual([['gifts', 1, 'product']]);
    const payload = submitted.mock.calls[0][0];
    expect(payload.gifts[1]).toMatchObject({ product: 'mug', price: 10 });
    expect(payload.gifts[0].price).toBeUndefined();
  });

  it('derives the prices of all rows when the company changes', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(enterGifts, {
      company: 'parent',
      gifts: [
        { _row_id: 'a', product: 'pen', price: 2 },
        { _row_id: 'b', product: 'mug', price: 10 },
      ],
    });

    await selectOption('company', 'Subsidiary (+10 %)');
    await expect.element(field('gifts_0_price')).toHaveValue(3);
    await expect.element(field('gifts_1_price')).toHaveValue(15);
    await submit();

    expect(submitted.mock.calls[0][0].gifts.map((row: any) => row.price)).toEqual([3, 15]);
  });

  it('waits for a pending change before it submits', async () => {
    const { submitted, selectOption, submit } = renderTaskForm(enterGifts, twoRows());

    await selectOption('gifts_0_product', 'Pen');
    await submit();

    await expect.poll(() => submitted.mock.calls.length).toBe(1);
    expect(submitted.mock.calls[0][0].gifts[0]).toMatchObject({ product: 'pen', price: 2 });
  });
});
