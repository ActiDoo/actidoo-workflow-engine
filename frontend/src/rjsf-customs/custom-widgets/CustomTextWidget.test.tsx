// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema } from '@rjsf/utils';

import CustomTextWidget from './CustomTextWidget';

const schema: RJSFSchema = {
  type: 'object',
  properties: {
    amount: { type: 'number', title: 'Menge', default: 0 },
    name: { type: 'string', title: 'Name', default: 'x' },
  },
};

const renderForm = (props: Partial<React.ComponentProps<typeof Form>> = {}) =>
  render(
    <Form
      schema={schema}
      validator={validator}
      widgets={{ TextWidget: CustomTextWidget }}
      {...props}
    />
  );

const lastFormData = (onChange: ReturnType<typeof vi.fn>) =>
  onChange.mock.calls[onChange.mock.calls.length - 1][0].formData;

describe('CustomTextWidget', () => {
  it('selects the number on focus so typing replaces it', async () => {
    const onChange = vi.fn();
    renderForm({ onChange, formData: { amount: 5 } });
    const input = screen.getByLabelText('Menge');

    await userEvent.click(input);
    await userEvent.keyboard('42');

    expect(input).toHaveValue(42);
    expect(lastFormData(onChange)).toEqual({ amount: 42, name: 'x' });
  });

  it('keeps a cleared number field empty while editing and shows the default again on blur', async () => {
    renderForm();
    const input = screen.getByLabelText('Menge');

    await userEvent.click(input);
    await userEvent.keyboard('{Backspace}');
    expect(input).toHaveValue(null);

    await userEvent.tab();
    expect(input).toHaveValue(0);
  });

  it('leaves text fields unchanged', async () => {
    renderForm();
    const input = screen.getByLabelText('Name');

    await userEvent.click(input);
    await userEvent.keyboard('y');

    expect(input).toHaveValue('xy');
  });
});
