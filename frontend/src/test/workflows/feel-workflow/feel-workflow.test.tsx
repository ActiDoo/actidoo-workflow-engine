// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/FeelWorkflow — see ../README.md.
//
// FeelForm has a dynamic list (my_list_B) inside another one (my_list); the inner row
// contains a required field, number_d, with a hide-if condition. The fields involved:
//   globalA (default 2), globalB (default 4, required)     globalB hidden if globalA = 1
//   my_list[].number_a (default 8), number_b (required)     number_b hidden if this.number_a = 9
//   my_list[].my_list_B[].number_c (default 32)             hidden if parent.number_a = 7
//   my_list[].my_list_B[].number_d (required)               hidden if this.number_c = 33

import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import feelForm from './feel-form.fixture.json';

// FeelForm makes no requests; the mock only turns an unexpected one into a test failure.
vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const NUMBER_A = 'my_list_0_number_a';
const NUMBER_C = 'my_list_0_my_list_B_0_number_c';
const NUMBER_D = 'my_list_0_my_list_B_0_number_d';

// Adds an outer row and sets number_a = 9, which hides the outer row's required number_b.
// After that only the inner row (my_list_B's default row) can still block the submit.
const addOuterRow = async (form: ReturnType<typeof renderTaskForm>): Promise<void> => {
  await form.addListRow('Dynamic list (my_list)');
  await form.field(NUMBER_A).fill('9');
  await expect.element(form.field(NUMBER_D)).toBeVisible();
};

describe('FeelWorkflow — hide-if in nested dynamic lists', () => {
  it('shows and hides the inner required field with its condition', async () => {
    const form = renderTaskForm(feelForm);
    await addOuterRow(form);

    await form.field(NUMBER_C).fill('33');
    await expect.element(form.field(NUMBER_D)).not.toBeVisible();

    await form.field(NUMBER_C).fill('34');
    await expect.element(form.field(NUMBER_D)).toBeVisible();
  });

  it('does not submit while the inner required field is visible and empty', async () => {
    const form = renderTaskForm(feelForm);
    await addOuterRow(form);

    await form.submit();

    expect(form.submitted).not.toHaveBeenCalled();
  });

  it('submits after the inner required field was filled and then hidden', async () => {
    const form = renderTaskForm(feelForm);
    await addOuterRow(form);

    await form.field(NUMBER_D).fill('4');
    await form.field(NUMBER_C).fill('33');
    await expect.element(form.field(NUMBER_D)).not.toBeVisible();

    await form.submit();

    expect(form.submitted).toHaveBeenCalledTimes(1);
    // The hidden field's value stays in the payload. The backend drops hidden values
    // (validate_task_data); keeping it in the form brings it back if the field is shown again.
    const innerRow = form.submitted.mock.calls[0][0].my_list[0].my_list_B[0];
    expect(innerRow).toMatchObject({ number_c: 33, number_d: 4 });
  });

  it('submits after the inner required field was hidden without being filled', async () => {
    const form = renderTaskForm(feelForm);
    await addOuterRow(form);

    await form.field(NUMBER_C).fill('33');
    await expect.element(form.field(NUMBER_D)).not.toBeVisible();

    await form.submit();

    expect(form.submitted).toHaveBeenCalledTimes(1);
  });

  it('hides an inner field through a parent. reference', async () => {
    const form = renderTaskForm(feelForm);
    await addOuterRow(form);
    await expect.element(form.field(NUMBER_C)).toBeVisible();

    await form.field(NUMBER_A).fill('7');

    await expect.element(form.field(NUMBER_C)).not.toBeVisible();
  });
});
