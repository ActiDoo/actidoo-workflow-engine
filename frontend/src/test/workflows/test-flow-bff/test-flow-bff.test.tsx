// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlowBff — see ../README.md.

import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import form1 from './form1.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async importOriginal => ({
  ...(await importOriginal<object>()),
  fetchPost: vi.fn(async (url: string) => {
    if (url.endsWith('user/search_property_options')) {
      return { data: (await import('./form1.category-options.fixture.json')).default };
    }
    throw new Error(`Unexpected fetchPost in test: ${url}`);
  }),
}));

describe('Test Flow BFF — Form1', () => {
  it('submits a consistent payload after filling the form', async () => {
    const { user, submitted, field, submit, uploadFile, selectOption } = renderTaskForm(form1);

    await user.type(field('required_text'), 'Hello BFF');
    await user.type(field('short_code'), 'ABC');
    await selectOption('category', 'Beta Category');
    await uploadFile('attachment', new File(['Hallo'], 'note.txt', { type: 'text/plain' }));
    await user.click(field('trigger_error'));
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

  it('defaults the untouched checkbox to false in the payload', async () => {
    const { user, submitted, field, submit } = renderTaskForm(form1);

    await user.type(field('required_text'), 'Hello BFF');
    await submit();

    expect(submitted).toHaveBeenCalledTimes(1);
    expect(submitted.mock.calls[0][0]).toEqual({
      required_text: 'Hello BFF',
      trigger_error: false,
    });
  });

  it('blocks submission when the required field is missing', async () => {
    const { submitted, submit } = renderTaskForm(form1);

    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });

  it('blocks submission when minLength is violated', async () => {
    const { user, submitted, field, submit } = renderTaskForm(form1);

    await user.type(field('required_text'), 'H');
    await submit();

    expect(submitted).not.toHaveBeenCalled();
  });
});
