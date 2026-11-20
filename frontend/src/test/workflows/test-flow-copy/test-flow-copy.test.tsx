// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render } from '@testing-library/react';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import { addToast } from '@/store/ui/actions';
import { page } from 'vitest/browser';
import { Provider } from 'react-redux';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { legacy_createStore } from 'redux';
import { ThemeProvider } from '@ui5/webcomponents-react';
import { QueryClient, QueryClientProvider } from 'react-query';

import { I18nProvider } from '@/i18n';
import { SingleTaskHeader } from '@/pages/tasks/content/single-task/SingleTaskHeader';
import StartWorkflowPreview from '@/pages/start-workflow-preview/StartWorkflowPreview';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const source = 'b860ab40-6670-49a6-8abb-4d71f60afcd6';
const task = {
  id: 'completed-task',
  name: 'Form1',
  title: 'Original form',
  lane: 'Initiator',
  jsonschema: { type: 'object', properties: {} },
  uischema: {},
  assigned_to_me: true,
  state_completed: true,
};
const preview = {
  name: 'TestFlow_Copy',
  title: 'Copy preview',
  task: { ...task, id: 'prepared-task' },
};
const copyButton = () => page.getByRole('button', { name: 'Start new workflow with this data' });
const startButton = () => page.getByRole('button', { name: 'Start Workflow with this data' });

function renderCopy(path = `/tasks/completed/${source}`) {
  const store = legacy_createStore(() => ({
    data: {},
    ui: { loading: {} },
  }));
  const dispatch = vi.spyOn(store, 'dispatch');
  render(
    <I18nProvider>
      <Provider store={store}>
        <QueryClientProvider client={new QueryClient()}>
          <ThemeProvider>
            <MemoryRouter initialEntries={[path]}>
              <Routes>
                <Route
                  path="/tasks/completed/:workflowId"
                  element={
                    <SingleTaskHeader task={task} reloadTask={vi.fn()} backToList={vi.fn()} />
                  }
                />
                <Route
                  path="/tasks/open/start_workflow_preview"
                  element={<StartWorkflowPreview />}
                />
              </Routes>
            </MemoryRouter>
          </ThemeProvider>
        </QueryClientProvider>
      </Provider>
    </I18nProvider>
  );

  return dispatch;
}

it('stays on the original task until prepared, displays the result once, and starts only on confirmation', async () => {
  let finish!: () => void;
  const pending = new Promise<void>(resolve => {
    finish = resolve;
  });
  const prepare = vi.fn(async () => {
    await pending;
    return { data: preview };
  });
  useFakeBackend(async call => {
    expect(call.url).toMatch(/user\/start_workflow_preview_with_data$/);
    expect(call.body).toEqual({ copy_from: source });
    return await prepare();
  });
  const dispatch = renderCopy();
  await copyButton().click();
  await expect.element(copyButton()).toBeDisabled();
  await expect.element(page.getByText('Original form')).toBeVisible();
  finish();
  await expect.element(page.getByText('Copy preview')).toBeVisible();
  expect(dispatch).not.toHaveBeenCalledWith(
    postRequest(WeDataKey.START_WORKFLOW, { copy_from: source })
  );
  await startButton().click();
  expect(prepare).toHaveBeenCalledTimes(1);
  expect(dispatch).toHaveBeenCalledWith(
    postRequest(WeDataKey.START_WORKFLOW, { copy_from: source })
  );
});

it('keeps a failed copy on the original task and lets the user retry', async () => {
  const prepare = vi
    .fn()
    .mockResolvedValueOnce({ data: {}, response: 403 })
    .mockResolvedValue({ data: preview });
  useFakeBackend(prepare);
  const dispatch = renderCopy();
  await copyButton().click();
  await vi.waitFor(() => {
    expect(dispatch).toHaveBeenCalledWith(addToast(<>Could not copy workflow.</>));
  });
  await expect.element(copyButton()).toBeEnabled();
  await copyButton().click();
  await expect.element(page.getByText('Copy preview')).toBeVisible();
  expect(prepare).toHaveBeenCalledTimes(2);
});

it('loads a directly opened copy preview from its source', async () => {
  const prepare = vi.fn().mockResolvedValue({ data: preview });
  useFakeBackend(prepare);
  renderCopy(`/tasks/open/start_workflow_preview?copy_from=${source}`);
  await expect.element(startButton()).toBeEnabled();
  expect(prepare).toHaveBeenCalledTimes(1);
  expect(prepare).toHaveBeenCalledWith(expect.objectContaining({ body: { copy_from: source } }));
});
