// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlow_DynamicListHidden — see ../README.md.

import { page } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import form010 from './form010-fill.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

useFakeBackend(({ url, body }) => {
  if (url.endsWith('user/strip_hidden_fields')) {
    return { data: { form_data: (body as { form_data: unknown }).form_data } };
  }
  throw new Error(`Unexpected request in test: ${url}`);
});

describe('Test Flow Dynamic List Hidden — list overview', () => {
  it('copies a column to the clipboard', async () => {
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    const { field, addListRow, selectOption } = renderTaskForm(form010);

    await selectOption('create_set', 'yes');
    await field('outer_list_0_outer_text').fill('UK5');
    await addListRow('Outer list');
    await field('outer_list_1_outer_text').fill('UK6');

    await page.getByRole('button', { name: 'Overview', exact: true }).first().click();
    await page.getByRole('button', { name: 'Copy column' }).click();

    await expect.poll(() => writeText.mock.calls).toEqual([['UK5\r\nUK6']]);
  });
});
