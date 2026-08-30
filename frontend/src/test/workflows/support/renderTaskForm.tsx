// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Renders TaskForm the way SingleTask does: the schema goes through
// changeRequiredDefinitionForFieldsWithHideIfDefinition, formData is controlled and mirrored
// into formContext.formData (hide-if reads it from there), HTML5 validation is on, and there
// is a router because the dynamic-list template only adds its default rows under /tasks/open/.
// The captured formData equals the request body of POST user/submit_task_data:
// SingleTask.submitData sends it unchanged.
//
// Interaction goes through Vitest's browser locators (real input, shadow DOM included, retry
// until the test times out), so tests do not need to wait for anything themselves.

import { useState } from 'react';
import _ from 'lodash';
import { render } from '@testing-library/react';
import { page, type Locator } from 'vitest/browser';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { legacy_createStore } from 'redux';
import { QueryClient, QueryClientProvider } from 'react-query';
import { ThemeProvider } from '@ui5/webcomponents-react';
import type { IChangeEvent } from '@rjsf/core';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import TaskForm from '@/rjsf-customs/components/TaskForm';
import { I18nProvider } from '@/i18n';
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
      onChange={(event: IChangeEvent) => {
        setFormData(_.cloneDeep(event.formData ?? {}));
      }}
      onSubmit={(event: IChangeEvent) => {
        onSubmit(event.formData);
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
  const submitted = vi.fn();
  const store = legacy_createStore(() => ({}));
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  render(
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <I18nProvider>
            <MemoryRouter initialEntries={[`/tasks/open/${TEST_TASK_ID}`]}>
              <TaskFormHarness fixture={fixture} onSubmit={submitted} />
            </MemoryRouter>
          </I18nProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </Provider>
  );

  // A form field by its rjsf id ("root_<key>", inside lists "root_<list>_<index>_<key>") —
  // stable, unlike display labels. A field hidden by hide-if is still in the DOM as
  // <input type="hidden"> under the same id, so `expect.element(field(key)).toBeVisible()`
  // tells visible from hidden.
  const field = (key: string): Locator => page.getById(`root_${key}`);

  // Clicks "Add" on the dynamic list with the given label (ui:label in the uischema). The
  // template has no id and the label no htmlFor, so the list is found from the label's
  // parent; nested lists have their own "Add" inside the rows, the list's own comes last.
  const addListRow = async (listLabel: string): Promise<void> => {
    const label = await page.getByText(listLabel, { exact: true }).findElement();
    const list = page.elementLocator(label.parentElement as HTMLElement);
    await list.getByRole('button', { name: 'Add', exact: true }).last().click();
  };

  // The native file input sits in the shadow root of ui5-file-uploader without role or
  // label — the one place where a CSS locator is needed.
  const uploadFile = async (key: string, file: File): Promise<void> => {
    await field(key).getByCss('input[type="file"]').upload(file);
    await expect.element(page.getByText(file.name, { exact: true })).toBeVisible();
  };

  // Opens a react-select based combobox and picks an option once it is loaded. The input
  // carrying the id is a scaled-down dummy when the select is not searchable (few
  // options) and cannot be clicked, so the menu is opened from the control around it.
  const selectOption = async (key: string, label: string): Promise<void> => {
    const input = await field(key).findElement();
    const control = input.closest('[class*="-control"]') ?? input;
    await page.elementLocator(control as HTMLElement).click();
    await page.getByRole('option', { name: label, exact: true }).click();
  };

  const submit = async (): Promise<void> => {
    await page.getByRole('button', { name: 'Absenden' }).click();
  };

  return { submitted, field, addListRow, uploadFile, selectOption, submit };
};
