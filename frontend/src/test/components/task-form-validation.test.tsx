// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { page, userEvent } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import form010 from '@/test/workflows/test-flow-form-semantics/form010-cases.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

// Exercise required widgets with the same schemas that workflow authors use.
const { properties } = form010.jsonschema;
const ui = form010.uischema;
const controls = {
  jsonschema: {
    type: 'object',
    required: ['confirmation', 'category', 'tags_optional', 'required_positions'],
    properties: {
      confirmation: { type: 'boolean', const: true },
      category: properties.category,
      hide_defaults: properties.hide_defaults,
      tags_optional: { ...properties.tags_optional, minItems: 1 },
      required_positions: {
        ...properties.required_positions,
        hideif: properties.tags_optional.hideif,
      },
      amount: properties.amount,
    },
  },
  uischema: {
    'ui:layout': {
      confirmation: ['confirmation'],
      category: ['category'],
      hide: ['hide_defaults'],
      tags: ['tags_optional'],
      positions: ['required_positions'],
      amount: ['amount'],
    },
    amount: ui.amount,
    category: ui.category,
    tags_optional: ui.tags_optional,
    required_positions: {
      ...ui.required_positions,
      'ui:hideif': ui.tags_optional['ui:hideif'],
      'ui:defaultRepetitions': 0,
    },
  },
};
const valid = {
  confirmation: true,
  category: 'a',
  tags_optional: ['a'],
  required_positions: [{}],
  hide_defaults: false,
};

describe('TaskForm validation', () => {
  it.each(['current', 'legacy'])(
    'requires a checkbox to be ticked in a %s schema',
    async version => {
      const fixture = structuredClone(controls);
      if (version === 'legacy')
        Reflect.deleteProperty(fixture.jsonschema.properties.confirmation, 'const');
      const { field, submitted, submit } = renderTaskForm(fixture, valid);
      await field('confirmation').click();
      await submit();
      await expect
        .element(field('confirmation__error'))
        .toHaveTextContent('Please tick this checkbox.');
      expect(
        (await field('confirmation__error').findElement()).querySelectorAll('li')
      ).toHaveLength(1);
      expect(submitted).not.toHaveBeenCalled();
      await field('confirmation').click();
      await submit();
      expect(submitted).toHaveBeenCalledOnce();
      expect(submitted.mock.calls[0][0].confirmation).toBe(true);
    }
  );

  it('leaves an unanswered confirmation unchecked', async () => {
    const { field, submit, submitted } = renderTaskForm(controls, {
      ...valid,
      confirmation: undefined,
    });
    await expect.element(field('confirmation')).not.toBeChecked();
    await submit();
    expect(submitted).not.toHaveBeenCalled();
    await field('confirmation').click();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
  });

  it('rejects a cleared required selection until an option is selected', async () => {
    const { field, selectOption, submitted, submit } = renderTaskForm(controls, valid);
    (await field('category').findElement()).focus();
    await userEvent.keyboard('{Backspace}');
    await submit();
    await expect.element(field('category__error')).toHaveTextContent('Please fill in this field.');
    expect(submitted).not.toHaveBeenCalled();
    await selectOption('category', 'Value a');
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
  });

  it.each([
    ['required_positions', 'Delete'],
    ['tags_optional', 'Remove Value a'],
  ])('validates an empty %s only while visible', async (key, removeButton) => {
    const { field, submitted, submit } = renderTaskForm(controls, valid);
    await page.getByRole('button', { name: removeButton, exact: true }).click();
    await submit();
    await expect
      .element(field(key + '__error'))
      .toHaveTextContent('Please add at least one entry.');
    expect(submitted).not.toHaveBeenCalled();
    await field('hide_defaults').click();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
  });

  it.each([
    { key: 'required_positions', value: [], message: 'Bitte füge mindestens einen Eintrag hinzu.' },
    { key: 'tags_optional', value: [], message: 'Bitte füge mindestens einen Eintrag hinzu.' },
    { key: 'category', value: null, message: 'Bitte fülle dieses Feld aus.' },
    { key: 'confirmation', value: false, message: 'Bitte kreuze dieses Kästchen an.' },
  ])('shows the German error for a draft with an empty $key', async ({ key, value, message }) => {
    const language = vi.spyOn(navigator, 'language', 'get').mockReturnValue('de-DE');
    try {
      const { field, submitted, submit } = renderTaskForm(controls, { ...valid, [key]: value });
      await submit();
      await expect.element(field(key + '__error')).toHaveTextContent(message);
      expect(document.querySelectorAll('#single-task-form [id$="__error"]')).toHaveLength(1);
      expect(submitted).not.toHaveBeenCalled();
    } finally {
      language.mockRestore();
    }
  });

  it('rejects an incomplete optional number', async () => {
    const { field, submitted, submit } = renderTaskForm(controls, valid);
    await field('amount').click();
    await userEvent.keyboard('1e');
    const input = (await field('amount').findElement()) as HTMLInputElement;
    expect(input.validity.badInput).toBe(true);
    expect(input.form?.noValidate).toBe(false);
    await submit();
    await expect
      .element(field('amount__error'))
      .toHaveTextContent('Please enter a complete number.');
    expect(submitted).not.toHaveBeenCalled();
    await field('amount').fill('10');
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0].amount).toBe(10);
  });
});
