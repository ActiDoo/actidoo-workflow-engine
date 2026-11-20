// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render } from '@testing-library/react';
import { page } from 'vitest/browser';
import { Provider } from 'react-redux';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { legacy_createStore } from 'redux';
import { ThemeProvider } from '@ui5/webcomponents-react';

import { I18nProvider } from '@/i18n';
import { SingleTaskHeader } from '@/pages/tasks/content/single-task/SingleTaskHeader';
import StartWorkflowPreview from '@/pages/start-workflow-preview/StartWorkflowPreview';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';

it('uses the completed instance as the source for both preview and start', async () => {
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
  const store = legacy_createStore(() => ({
    data: { [WeDataKey.START_WORKFLOW_PREVIEW]: { data: { task, title: 'Copy' } } },
    ui: { loading: {} },
  }));
  const dispatch = vi.spyOn(store, 'dispatch');
  render(
    <I18nProvider>
      <Provider store={store}>
        <ThemeProvider>
          <MemoryRouter initialEntries={[`/tasks/completed/${source}`]}>
            <Routes>
              <Route
                path="/tasks/completed/:workflowId"
                element={<SingleTaskHeader task={task} reloadTask={vi.fn()} backToList={vi.fn()} />}
              />
              <Route path="/tasks/open/start_workflow_preview" element={<StartWorkflowPreview />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      </Provider>
    </I18nProvider>
  );

  await page.getByRole('button', { name: 'Start new workflow with this data' }).click();
  expect(dispatch).toHaveBeenCalledWith(
    postRequest(WeDataKey.START_WORKFLOW_PREVIEW, { copy_from: source })
  );
  await page.getByRole('button', { name: 'Start Workflow with this data' }).click();
  expect(dispatch).toHaveBeenCalledWith(
    postRequest(WeDataKey.START_WORKFLOW, { copy_from: source })
  );
});
