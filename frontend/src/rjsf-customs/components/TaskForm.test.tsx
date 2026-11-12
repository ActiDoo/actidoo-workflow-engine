// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { RJSFSchema } from '@rjsf/utils';

import { I18nProvider } from '@/i18n';
import TaskForm, { taskFormValidator } from '@/rjsf-customs/components/TaskForm';

const schema: RJSFSchema = {
  type: 'object',
  properties: {
    name: { type: 'string', title: 'Name' },
    note: { type: 'string', title: 'Notiz' },
  },
};

const renderForm = (onSubmit: () => void) =>
  render(
    <I18nProvider>
      <TaskForm
        schema={schema}
        uiSchema={{ note: { 'ui:widget': 'textarea' } }}
        templates={{}}
        onSubmit={onSubmit}>
        <button type="submit">Absenden</button>
      </TaskForm>
    </I18nProvider>
  );

describe('TaskForm', () => {
  it('leaves nested Python patterns to the backend and keeps other validation', () => {
    const nestedSchema: RJSFSchema = {
      type: 'object',
      properties: {
        rows: {
          type: 'array',
          items: {
            type: 'object',
            required: ['code'],
            properties: { code: { type: 'string', pattern: '^(?P<code>[A-Z]{2})$', minLength: 2 } },
          },
        },
      },
    };
    expect(
      taskFormValidator.validateFormData({ rows: [{ code: 'wrong' }] }, nestedSchema).errors
    ).toEqual([]);
    expect(
      taskFormValidator.validateFormData({ rows: [{ code: 'x' }] }, nestedSchema).errors
    ).toEqual(expect.arrayContaining([expect.objectContaining({ name: 'minLength' })]));
    expect(taskFormValidator.validateFormData({ rows: [{}] }, nestedSchema).errors).toEqual(
      expect.arrayContaining([expect.objectContaining({ name: 'required' })])
    );
  });

  it('shows server errors, preserves the input and allows a corrected retry', async () => {
    const onSubmit = vi.fn();
    const form = (extraErrors = {}) => (
      <I18nProvider>
        <TaskForm
          schema={{
            type: 'object',
            properties: {
              code: { type: 'string', title: 'Code', pattern: '^(?P<code>[A-Z]{2})$' },
            },
          }}
          templates={{}}
          extraErrors={extraErrors}
          onSubmit={onSubmit}>
          <button type="submit">Absenden</button>
        </TaskForm>
      </I18nProvider>
    );
    const { rerender } = render(form());
    await userEvent.type(screen.getByLabelText('Code'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Absenden' }));
    expect(onSubmit).toHaveBeenCalledTimes(1);

    rerender(form({ code: { __errors: ['Zwei Großbuchstaben eingeben'] } }));
    expect(screen.getByText('Zwei Großbuchstaben eingeben')).toBeVisible();
    expect(screen.getByLabelText('Code')).toHaveValue('wrong');
    await userEvent.clear(screen.getByLabelText('Code'));
    await userEvent.type(screen.getByLabelText('Code'), 'AB');
    await userEvent.click(screen.getByRole('button', { name: 'Absenden' }));
    expect(onSubmit).toHaveBeenCalledTimes(2);
    expect(onSubmit.mock.calls[1][0].formData).toEqual({ code: 'AB' });
  });

  it('does not submit when Enter is pressed in a text field', async () => {
    const onSubmit = vi.fn();
    renderForm(onSubmit);

    await userEvent.type(screen.getByLabelText('Name'), 'Max{Enter}');

    expect(screen.getByLabelText('Name')).toHaveValue('Max');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('keeps Enter as a line break in a textarea', async () => {
    const onSubmit = vi.fn();
    renderForm(onSubmit);

    await userEvent.type(screen.getByLabelText('Notiz'), 'a{Enter}b');

    expect(screen.getByLabelText('Notiz')).toHaveValue('a\nb');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits via the submit button', async () => {
    const onSubmit = vi.fn();
    renderForm(onSubmit);

    await userEvent.type(screen.getByLabelText('Name'), 'Max');
    await userEvent.click(screen.getByRole('button', { name: 'Absenden' }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0].formData).toEqual({ name: 'Max' });
  });
});
