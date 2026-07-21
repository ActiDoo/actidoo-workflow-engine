// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema } from '@rjsf/utils';

import CustomCheckbox from './CustomCheckbox';

const schema: RJSFSchema = {
  type: 'object',
  properties: {
    agree: { type: 'boolean', title: 'Zustimmung' },
  },
};

const renderForm = (props: Partial<React.ComponentProps<typeof Form>> = {}) =>
  render(
    <Form
      schema={schema}
      validator={validator}
      widgets={{ CheckboxWidget: CustomCheckbox }}
      {...props}
    />
  );

describe('CustomCheckbox', () => {
  it('renders unchecked with its label when no value is set', () => {
    renderForm();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByText('Zustimmung')).toBeInTheDocument();
  });

  it('renders checked when formData is true', () => {
    renderForm({ formData: { agree: true } });
    expect(screen.getByRole('checkbox')).toBeChecked();
  });

  it('propagates a click as form data change', async () => {
    const onChange = vi.fn();
    renderForm({ onChange });

    await userEvent.click(screen.getByRole('checkbox'));

    expect(screen.getByRole('checkbox')).toBeChecked();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1];
    expect(lastCall[0].formData).toEqual({ agree: true });
  });

  it('marks required fields with an asterisk in the label', () => {
    renderForm({ schema: { ...schema, required: ['agree'] } });
    expect(screen.getByText('Zustimmung*')).toBeInTheDocument();
  });
});
