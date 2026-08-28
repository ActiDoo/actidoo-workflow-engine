// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlow_DynamicListHidden — see ../README.md.
//
// One select drives three dynamic lists. "no" shows the inner list (inside the outer
// list's row) whose only field is required; "yes" hides it again. Every list starts with
// one default row, created when the list is first shown.

import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import form010 from './form010-fill.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

useFakeBackend(({ url }) => {
  throw new Error(`Unexpected request in test: ${url}`);
});

const INNER_REQUIRED = 'outer_list_0_inner_list_0_inner_required';

describe('Test Flow Dynamic List Hidden — Form010', () => {
  it('submits although a hidden inner list carries an empty required field', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(form010);

    // "no" shows the inner list, which creates its default row with the empty required field.
    await selectOption('create_set', 'no');
    await expect.element(field(INNER_REQUIRED)).toBeVisible();

    // "yes" hides the inner list again; the row stays in the form data.
    await selectOption('create_set', 'yes');
    await expect.element(field(INNER_REQUIRED)).not.toBeInTheDocument();

    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    // The hidden row is still sent - stripping hidden data is the backend's job.
    const payload = submitted.mock.calls[0][0];
    expect(payload).toMatchObject({ create_set: 'yes' });
    expect(payload.outer_list[0].inner_list).toHaveLength(1);
  });

  it('blocks the submit while the inner list is shown and its required field is empty', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(form010);

    await selectOption('create_set', 'no');
    await expect.element(field(INNER_REQUIRED)).toBeVisible();

    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });

  it('submits once the shown required field is filled', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(form010);

    await selectOption('create_set', 'no');
    await field(INNER_REQUIRED).fill('filled');
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    expect(submitted.mock.calls[0][0]).toMatchObject({
      create_set: 'no',
      outer_list: [{ inner_list: [{ inner_required: 'filled' }] }],
    });
  });

  it('validates the required field again once the inner list is shown again', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(form010);

    await selectOption('create_set', 'no');
    await expect.element(field(INNER_REQUIRED)).toBeVisible();
    await selectOption('create_set', 'yes');
    await expect.element(field(INNER_REQUIRED)).not.toBeInTheDocument();
    await selectOption('create_set', 'no');
    await expect.element(field(INNER_REQUIRED)).toBeVisible();

    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });

  it('submits right away with "yes" - the hidden inner list never got a row', async () => {
    const { submitted, field, selectOption, submit } = renderTaskForm(form010);

    await selectOption('create_set', 'yes');
    await expect.element(field('outer_list_0_outer_text')).toBeVisible();
    await expect.element(field(INNER_REQUIRED)).not.toBeInTheDocument();

    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
  });
});
