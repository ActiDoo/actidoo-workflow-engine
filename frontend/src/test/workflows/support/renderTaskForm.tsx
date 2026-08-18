// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Renders TaskForm the way SingleTask does: the schema goes through
// changeRequiredDefinitionForFieldsWithHideIfDefinition, formData is controlled and mirrored
// into formContext.formData (hide-if reads it from there), HTML5 validation is on, and there
// is a router because the dynamic-list template only adds its default rows under /tasks/open/.
// The captured formData equals the request body of POST user/submit_task_data:
// SingleTask.submitData sends it unchanged.

import { useState } from 'react';
import _ from 'lodash';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { legacy_createStore } from 'redux';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ThemeProvider } from '@ui5/webcomponents-react';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import TaskForm from '@/rjsf-customs/components/TaskForm';
import { changeRequiredDefinitionForFieldsWithHideIfDefinition } from '@/services/FeelService';

export const TEST_TASK_ID = 'workflow-test-task';

export interface WorkflowFormFixture {
  jsonschema: unknown;
  uischema: unknown;
}

const TaskFormHarness = ({
  fixture,
  onSubmit,
}: {
  fixture: WorkflowFormFixture;
  onSubmit: (formData: unknown) => void;
}) => {
  const [formData, setFormData] = useState<Record<string, unknown>>({});

  const schema = _.cloneDeep(fixture.jsonschema) as RJSFSchema;
  const uiSchema = _.cloneDeep(fixture.uischema) as UiSchema;
  changeRequiredDefinitionForFieldsWithHideIfDefinition(schema, uiSchema);

  return (
    <TaskForm
      formData={formData}
      schema={schema}
      uiSchema={uiSchema}
      showErrorList={false}
      noHtml5Validate={false}
      onChange={(data: any) => {
        setFormData(_.cloneDeep(data.formData ?? {}));
      }}
      onSubmit={(data: any) => {
        onSubmit(data.formData);
      }}
      formContext={{
        formData,
        schema: fixture.jsonschema,
        uiSchema: fixture.uischema,
        taskId: TEST_TASK_ID,
      }}>
      <button type="submit">Absenden</button>
    </TaskForm>
  );
};

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
          <MemoryRouter initialEntries={[`/tasks/open/${TEST_TASK_ID}`]}>
            <TaskFormHarness fixture={fixture} onSubmit={submitted} />
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </Provider>
  );

  // Selects by RJSF field id ("root_<key>", inside lists "root_<list>_<index>_<key>") —
  // stable, unlike display labels.
  const field = (key: string): HTMLElement => {
    const id = `root_${key}`;
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`No form field with id "${id}" found`);
    }
    return element;
  };
  // A field hidden by hide-if is still in the DOM as <input type="hidden"> under the same
  // id, so a field counts as visible only if it exists and is not a hidden input.
  const isFieldVisible = (key: string): boolean => {
    const element = document.getElementById(`root_${key}`);
    return element !== null && (element as HTMLInputElement).type !== 'hidden';
  };

  // Rows and visibility do not update synchronously: the list template adds default rows on
  // a timer (one per nesting level), and hide-if is re-evaluated with a throttle while the
  // user types. Wait for the expected state instead of asserting right after an action.
  const waitForField = async (key: string): Promise<HTMLElement> =>
    await waitFor(
      () => {
        if (!isFieldVisible(key)) {
          throw new Error(`Form field "root_${key}" is not visible`);
        }
        return field(key);
      },
      { timeout: 3000 }
    );
  const waitForFieldHidden = async (key: string): Promise<void> => {
    await waitFor(() => {
      if (isFieldVisible(key)) {
        throw new Error(`Form field "root_${key}" is still visible`);
      }
    });
  };

  // Replaces the value of a text or number input. user.clear() is not enough for fields
  // with a schema default: RJSF puts the default back the moment the field is empty, so
  // the typed value would be appended to it.
  const replaceValue = async (key: string, value: string): Promise<void> => {
    await user.tripleClick(field(key));
    await user.keyboard(value);
  };

  // Clicks "Add" on the dynamic list with the given label (ui:label in the uischema).
  const addListRow = async (listLabel: string): Promise<void> => {
    const label = Array.from(document.querySelectorAll('label.form-label')).find(
      element => element.textContent === listLabel
    );
    const addButton = Array.from(label?.parentElement?.querySelectorAll('ui5-button') ?? []).find(
      button => button.textContent === 'Add'
    );
    if (!addButton) {
      throw new Error(`No "Add" button for dynamic list "${listLabel}" found`);
    }
    await user.click(addButton);
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

  return {
    user,
    submitted,
    field,
    isFieldVisible,
    waitForField,
    waitForFieldHidden,
    replaceValue,
    addListRow,
    submit,
    uploadFile,
    selectOption,
  };
};
