// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlowBff — see ../README.md.

import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import form1 from './form1.fixture.json';
import categoryOptions from './form1.category-options.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

// The dynamic select loads its options from the BFF; everything else is unexpected.
useFakeBackend(({ url }) => {
  if (url.endsWith('user/search_property_options')) return { data: categoryOptions };
  throw new Error(`Unexpected request in test: ${url}`);
});

describe('Test Flow BFF — Form1', () => {
  it('submits a consistent payload after filling the form', async () => {
    const { submitted, field, submit, uploadFile, selectOption } = renderTaskForm(form1);

    await field('required_text').fill('Hello BFF');
    await field('short_code').fill('ABC');
    await selectOption('category', 'Beta Category');
    await uploadFile('attachment', new File(['Hallo'], 'note.txt', { type: 'text/plain' }));
    await field('trigger_error').click();
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    expect(submitted).toHaveBeenCalledWith({
      required_text: 'Hello BFF',
      short_code: 'ABC',
      category: 'cat_beta',
      attachment: {
        filename: 'note.txt',
        mimetype: 'text/plain',
        datauri: 'data:text/plain;name=note.txt;base64,SGFsbG8=',
      },
      trigger_error: true,
    });
  });

  it('defaults the untouched checkbox to false and omits all untouched fields', async () => {
    const { submitted, field, submit } = renderTaskForm(form1);

    await field('required_text').fill('Hello BFF');
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    const payload = submitted.mock.calls[0][0];
    expect(payload).toEqual({
      required_text: 'Hello BFF',
      trigger_error: false,
    });
    expect(payload).not.toHaveProperty('short_code');
    expect(payload).not.toHaveProperty('category');
    expect(payload).not.toHaveProperty('attachment');
    expect(payload).not.toHaveProperty('optional_note');
  });

  it('blocks submission when the required field is missing', async () => {
    const { submitted, submit } = renderTaskForm(form1);

    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });

  it('blocks submission when minLength is violated', async () => {
    const { submitted, field, submit } = renderTaskForm(form1);

    await field('required_text').fill('H');
    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });
});
