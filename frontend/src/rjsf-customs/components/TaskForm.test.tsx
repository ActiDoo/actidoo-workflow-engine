// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { RJSFSchema } from '@rjsf/utils';

import TaskForm from './TaskForm';

const schema: RJSFSchema = {
  type: 'object',
  properties: {
    name: { type: 'string', title: 'Name' },
    note: { type: 'string', title: 'Notiz' },
  },
};

const renderForm = (onSubmit: () => void) =>
  render(
    <TaskForm
      schema={schema}
      uiSchema={{ note: { 'ui:widget': 'textarea' } }}
      templates={{}}
      onSubmit={onSubmit}>
      <button type="submit">Absenden</button>
    </TaskForm>
  );

describe('TaskForm', () => {
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
