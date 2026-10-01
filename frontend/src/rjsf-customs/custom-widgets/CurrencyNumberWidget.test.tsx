// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import { I18nProvider } from '@/i18n';
import CurrencyNumberWidget from '@/rjsf-customs/custom-widgets/CurrencyNumberWidget';

// An emptied amount is whatever the form declares as empty: null in forms handed out
// since empty fields are null, nothing in tasks of older running instances whose schema
// has no null - sending null there would block the submit with a type error.
const renderAmount = (schemaType: RJSFSchema['type'], uiSchema: UiSchema) => {
  const onChange = vi.fn();
  render(
    <I18nProvider>
      <Form
        schema={{ type: 'object', properties: { amount: { type: schemaType } } }}
        uiSchema={{ amount: { 'ui:widget': CurrencyNumberWidget, ...uiSchema } }}
        formData={{ amount: 12 }}
        validator={validator}
        onChange={onChange}
      />
    </I18nProvider>
  );
  return onChange;
};

const clearAmount = async (): Promise<void> => {
  const input = screen.getByRole('textbox');
  await userEvent.clear(input);
  await userEvent.tab();
};

describe('CurrencyNumberWidget', () => {
  it('sends null for an emptied amount when the form declares null as empty', async () => {
    const onChange = renderAmount(['number', 'null'], { 'ui:emptyValue': null });

    await clearAmount();

    expect(onChange.mock.lastCall?.[0].formData).toEqual({ amount: null });
  });

  it('leaves an emptied amount out in an older form without null', async () => {
    const onChange = renderAmount('number', {});

    await clearAmount();

    expect(onChange.mock.lastCall?.[0].formData.amount).toBeUndefined();
  });
});
