// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render } from '@testing-library/react';
import { page } from 'vitest/browser';
import { Provider } from 'react-redux';
import { legacy_createStore } from 'redux';
import { ThemeProvider } from '@ui5/webcomponents-react';
import { I18nProvider } from '@/i18n';
import WeEditableDataSection from '@/utils/components/WeEditableDataSection';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';

const renderEditor = () => {
  const store = legacy_createStore(() => ({ data: {}, ui: { loading: {} } }));
  const dispatch = vi.spyOn(store, 'dispatch');
  render(
    <I18nProvider>
      <Provider store={store}>
        <ThemeProvider>
          <WeEditableDataSection taskId="task-1" data={{ name: 'Before' }} />
        </ThemeProvider>
      </Provider>
    </I18nProvider>
  );
  return dispatch;
};

it('previews unsaved JSON and keeps it when returning to the editor and saving', async () => {
  const dispatch = renderEditor();
  const draft = '{"name":"After","count":0}';
  await page.getByRole('textbox').fill(draft);
  await page.getByRole('button', { name: 'Tree view', exact: true }).click();
  await expect.element(page.getByText('"After"', { exact: true })).toBeVisible();
  await expect.element(page.getByText('"Before"', { exact: true })).not.toBeInTheDocument();
  await page.getByRole('button', { name: 'Edit JSON', exact: true }).click();
  await expect.element(page.getByRole('textbox')).toHaveValue(draft);
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(dispatch).toHaveBeenCalledWith(
    postRequest(WeDataKey.ADMIN_REPLACE_TASK_DATA, {
      task_id: 'task-1',
      data: { name: 'After', count: 0 },
    })
  );
});

it('blocks the preview for invalid or cleared JSON and enables it again after correction', async () => {
  renderEditor();
  for (const draft of ['{', '']) {
    await page.getByRole('textbox').fill(draft);
    await expect
      .element(page.getByRole('button', { name: 'Tree view', exact: true }))
      .toBeDisabled();
  }
  await page.getByRole('textbox').fill('null');
  await page.getByRole('button', { name: 'Tree view', exact: true }).click();
  await expect.element(page.getByText('null', { exact: true })).toBeVisible();
});
