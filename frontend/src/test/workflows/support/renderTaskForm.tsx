// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// The captured formData equals the request body of POST user/submit_task_data:
// SingleTask.submitData sends it unchanged.

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { legacy_createStore } from 'redux';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ThemeProvider } from '@ui5/webcomponents-react';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import TaskForm from '@/rjsf-customs/components/TaskForm';

export const TEST_TASK_ID = 'workflow-test-task';

export interface WorkflowFormFixture {
  jsonschema: unknown;
  uischema: unknown;
}

export const renderTaskForm = (fixture: WorkflowFormFixture) => {
  const user = userEvent.setup();
  const submitted = vi.fn();
  const store = legacy_createStore(() => ({}));
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <TaskForm
            schema={fixture.jsonschema as RJSFSchema}
            uiSchema={fixture.uischema as UiSchema}
            formContext={{ formData: {}, taskId: TEST_TASK_ID }}
            onSubmit={(data: any) => submitted(data.formData)}>
            <button type="submit">Absenden</button>
          </TaskForm>
        </ThemeProvider>
      </QueryClientProvider>
    </Provider>
  );

  // Selects by RJSF field id ("root_<key>") — stable, unlike display labels.
  const field = (key: string): HTMLElement => {
    const id = `root_${key}`;
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`No form field with id "${id}" found`);
    }
    return element;
  };

  // The FileUploader's native input lives in its shadow root, out of userEvent's reach.
  const uploadFile = async (key: string, file: File): Promise<void> => {
    const uploader = field(key).querySelector('ui5-file-uploader');
    if (!uploader) {
      throw new Error(`No ui5-file-uploader found inside field "${key}"`);
    }
    const input = await waitFor(() => {
      const candidate = uploader.shadowRoot?.querySelector<HTMLInputElement>('input[type="file"]');
      if (!candidate) {
        throw new Error(`File input of field "${key}" not rendered yet`);
      }
      return candidate;
    });

    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() => {
      if (!screen.queryByText(file.name)) {
        throw new Error(`File "${file.name}" not shown in the form yet`);
      }
    });
  };

  // Opens a react-select based combobox and picks an option once it is loaded.
  const selectOption = async (key: string, label: string): Promise<void> => {
    await user.click(field(key));
    await user.click(await screen.findByText(label));
  };

  const submit = async (): Promise<void> => {
    await user.click(screen.getByRole('button', { name: 'Absenden' }));
  };

  return { user, submitted, field, submit, uploadFile, selectOption };
};
