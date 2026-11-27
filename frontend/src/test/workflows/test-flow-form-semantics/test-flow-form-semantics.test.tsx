// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { cleanup } from '@testing-library/react';
import { page, userEvent } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import form010 from '@/test/workflows/test-flow-form-semantics/form010-cases.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

// SingleTask initializes static instruction fields to null before rendering.
const initialData = {
  ...Object.fromEntries(
    Object.entries(form010.jsonschema.properties)
      .filter(([, schema]) => schema.type === 'null')
      .map(([key]) => [key, null])
  ),
  text_optional: 'Sample',
  locked_text: 'set by the service task',
  locked_rows: [{ locked_item: 'set by the service task' }],
};

const errorsInForm = () => document.querySelectorAll('#single-task-form [id$="__error"]');

const fieldGroup = (key: string) =>
  page.getByCss(`[data-form-field-path='${JSON.stringify([key])}']`);

describe('Test Flow Form Semantics — validation on submit', () => {
  it('1b: reports only the empty required dynamic list', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, initialData);
    await fieldGroup('required_positions')
      .getByRole('button', { name: 'Delete', exact: true })
      .click();
    await submit();
    await expect
      .element(field('required_positions__error'))
      .toHaveTextContent('Please add at least one entry.');
    expect(errorsInForm()).toHaveLength(1);
    expect(submitted).not.toHaveBeenCalled();
  });

  it('3a: spaces in the sample text hide both conditional messages', async () => {
    const { field } = renderTaskForm(form010, initialData);
    const nullMessage = fieldGroup('Field_needs_text_null');
    const emptyStringMessage = fieldGroup('Field_needs_text_blank');
    await expect.element(nullMessage).toBeVisible();
    await expect.element(emptyStringMessage).toBeVisible();

    await field('text_optional').fill('   ');
    await expect.element(nullMessage).not.toBeInTheDocument();
    await expect.element(emptyStringMessage).not.toBeInTheDocument();
  });

  it('3b: an empty multi select hides both conditional messages', async () => {
    renderTaskForm(form010, { ...initialData, tags_for_empty_check: ['a'] });
    await expect.element(fieldGroup('Field_needs_tags')).toBeVisible();
    await expect.element(fieldGroup('Field_needs_tags_list')).toBeVisible();
    cleanup();

    const { field } = renderTaskForm(form010, { ...initialData, tags_for_empty_check: [] });
    await expect.element(field('text_optional')).toBeVisible();
    await expect.element(fieldGroup('Field_needs_tags')).not.toBeInTheDocument();
    await expect.element(fieldGroup('Field_needs_tags_list')).not.toBeInTheDocument();
  });

  it('4: reopens a cleared number without restoring the default', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, initialData);
    await expect.element(field('number_optional')).toHaveValue(5);
    await field('number_optional').fill('');
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    const saved = submitted.mock.calls[0][0];
    expect(saved.number_optional).toBeNull();

    cleanup();
    const reopened = renderTaskForm(form010, saved);
    await expect.element(reopened.field('number_optional')).toHaveValue(null);
  });

  it('2b: sends null for a cleared date with time', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, {
      ...initialData,
      datetime_optional: '2026-01-31T10:00:00.000Z',
    });
    await field('datetime_optional').clear();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0].datetime_optional).toBeNull();
  });

  it('11b: submits although a read-only value breaks its maximum length', async () => {
    const { submitted, submit } = renderTaskForm(form010, {
      ...initialData,
      locked_code: 'ABCDEF',
    });
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0].locked_code).toBe('ABCDEF');
  });

  it('13: shows the stored value of a hidden field again once it is visible', async () => {
    const { field } = renderTaskForm(form010, {
      ...initialData,
      hide_reason: true,
      kept_reason: 'Stored reason',
    });
    await expect.element(field('kept_reason')).not.toBeInTheDocument();
    await field('hide_reason').click();
    await expect.element(field('kept_reason')).toHaveValue('Stored reason');
  });

  it('11: locks the prefilled text', async () => {
    const { field } = renderTaskForm(form010, initialData);
    await expect.element(field('locked_text')).toBeDisabled();
    await expect.element(field('locked_text')).toHaveValue('set by the service task');
  });

  it('11: prevents adding a row to the read-only list', async () => {
    renderTaskForm(form010, initialData);
    await expect
      .element(fieldGroup('locked_rows').getByRole('button', { name: 'Add' }))
      .toBeDisabled();
  });

  it('12a: shows native and schema errors on the same submit', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, initialData);
    await field('combined_name').fill('');
    await field('combined_code').fill('A');
    expect(
      ((await field('combined_name').findElement()) as HTMLInputElement).validity.valueMissing
    ).toBe(true);
    expect(((await field('combined_code').findElement()) as HTMLInputElement).validity.valid).toBe(
      true
    );
    await submit();
    await expect
      .element(field('combined_name__error'))
      .toHaveTextContent('Please fill in this field.');
    await expect
      .element(field('combined_code__error'))
      .toHaveTextContent('Please enter at least 2 characters.');
    expect(errorsInForm()).toHaveLength(2);
    expect(submitted).not.toHaveBeenCalled();
    await expect.element(field('combined_name')).toHaveFocus();
    await field('combined_name').fill('Alex');
    await submit();
    await expect.element(field('combined_name__error')).not.toBeInTheDocument();
    await expect.element(field('combined_code__error')).toBeVisible();
    expect(submitted).not.toHaveBeenCalled();

    await field('combined_code').fill('AB');
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
  });

  it('12b: scrolls to the invalid field and lets the user type there', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, initialData);
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
    try {
      await field('focus_target').fill('A');
      await submit();
      await expect.element(field('focus_target')).toHaveFocus();
      expect(errorsInForm()).toHaveLength(1);
      expect(scroll.mock.contexts).toContain(await field('focus_target__error').findElement());
      expect(submitted).not.toHaveBeenCalled();
      await userEvent.keyboard('B');
      expect(((await field('focus_target').findElement()) as HTMLInputElement).value).toContain(
        'B'
      );
    } finally {
      scroll.mockRestore();
    }
  });

  it.each([
    ['de-DE', 'Der Wert muss mindestens 10 sein.'],
    ['en-US', 'The value must be at least 10.'],
  ])('12c: shows the numeric limit in %s', async (locale, message) => {
    const language = vi.spyOn(navigator, 'language', 'get').mockReturnValue(locale);
    try {
      const { field, submitted, submit } = renderTaskForm(form010, initialData);
      await field('minimum_quantity').fill('9');
      await submit();
      await expect.element(field('minimum_quantity__error')).toHaveTextContent(message);
      expect(errorsInForm()).toHaveLength(1);
      expect(submitted).not.toHaveBeenCalled();
    } finally {
      language.mockRestore();
    }
  });
});
