// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import CustomDateWidget from '@/rjsf-customs/custom-widgets/CustomDateWidget';

// A cleared date is whatever the form declares as empty: null in forms handed out since
// empty fields are null - so the stored date is cleared - and nothing in tasks of older
// running instances whose schema has no null.
const clearDate = async (schemaType: RJSFSchema['type'], uiSchema: UiSchema) => {
  const onChange = vi.fn();
  const { container } = render(
    <Form
      schema={{ type: 'object', properties: { due: { type: schemaType, format: 'date' } } }}
      uiSchema={{ due: uiSchema }}
      formData={{ due: '2026-01-02' }}
      validator={validator}
      widgets={{ DateWidget: CustomDateWidget }}
      onChange={onChange}
    />
  );
  await userEvent.clear(container.querySelector('input[type="date"]') as HTMLInputElement);
  return onChange.mock.lastCall?.[0].formData;
};

describe('CustomDateWidget', () => {
  it('sends null for a cleared date when the form declares null as empty', async () => {
    expect(await clearDate(['string', 'null'], { 'ui:emptyValue': null })).toEqual({ due: null });
  });

  it('leaves a cleared date out in an older form without null', async () => {
    expect((await clearDate('string', {})).due).toBeUndefined();
  });

  it('passes an entered date through', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <Form
        schema={{
          type: 'object',
          properties: { due: { type: ['string', 'null'], format: 'date' } },
        }}
        uiSchema={{ due: { 'ui:emptyValue': null } }}
        validator={validator}
        widgets={{ DateWidget: CustomDateWidget }}
        onChange={onChange}
      />
    );
    await userEvent.type(
      container.querySelector('input[type="date"]') as HTMLInputElement,
      '2026-03-04'
    );
    expect(onChange.mock.lastCall?.[0].formData).toEqual({ due: '2026-03-04' });
  });
});
