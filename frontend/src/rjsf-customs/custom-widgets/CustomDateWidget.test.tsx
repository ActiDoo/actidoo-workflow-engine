// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from '@rjsf/react-bootstrap';
import validator from '@rjsf/validator-ajv8';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import CustomDateWidget, {
  CustomDateTimeWidget,
} from '@/rjsf-customs/custom-widgets/CustomDateWidget';

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

// The engine declares a date with time as format "datetime".
const renderDateTime = (
  schemaType: RJSFSchema['type'],
  uiSchema: UiSchema,
  formData: Record<string, unknown>
): { input: HTMLInputElement; onChange: ReturnType<typeof vi.fn> } => {
  const onChange = vi.fn();
  const { container } = render(
    <Form
      schema={{ type: 'object', properties: { at: { type: schemaType, format: 'datetime' } } }}
      uiSchema={{ at: uiSchema }}
      formData={formData}
      validator={validator}
      widgets={{ DateTimeWidget: CustomDateTimeWidget }}
      onChange={onChange}
    />
  );
  return {
    input: container.querySelector('input[type="datetime-local"]') as HTMLInputElement,
    onChange,
  };
};

describe('CustomDateTimeWidget', () => {
  const stored = '2026-01-02T03:04:00.000Z';

  it('sends null for a cleared date with time when the form declares null as empty', async () => {
    const { input, onChange } = renderDateTime(
      ['string', 'null'],
      { 'ui:emptyValue': null },
      { at: stored }
    );
    await userEvent.clear(input);
    expect(onChange.mock.lastCall?.[0].formData).toEqual({ at: null });
  });

  it('leaves a cleared date with time out in an older form without null', async () => {
    const { input, onChange } = renderDateTime('string', {}, { at: stored });
    await userEvent.clear(input);
    expect(onChange.mock.lastCall?.[0].formData.at).toBeUndefined();
  });

  it('passes an entered date with time through, in UTC', async () => {
    const { input, onChange } = renderDateTime(['string', 'null'], { 'ui:emptyValue': null }, {});
    await userEvent.type(input, '2026-03-04T10:30');
    expect(onChange.mock.lastCall?.[0].formData).toEqual({
      at: new Date('2026-03-04T10:30').toJSON(),
    });
  });
});
