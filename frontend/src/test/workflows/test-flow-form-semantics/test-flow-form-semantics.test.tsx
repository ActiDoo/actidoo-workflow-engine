// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { page, userEvent } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import form010 from '@/test/workflows/test-flow-form-semantics/form010-cases.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

// The prepare step pre-fills the required controls for manual cases 1b and 1c.
const initialData = {
  required_positions: [{}],
  required_tags: ['a'],
  required_choice: 'a',
  hide_required_lists: false,
  confirm_review: true,
};

describe('Test Flow Form Semantics — validation on submit', () => {
  it('shows both visible list errors, scrolls to the first and accepts the hidden lists', async () => {
    const { field, submitted, submit } = renderTaskForm(form010, initialData);
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
    await page.getByRole('button', { name: 'Delete', exact: true }).first().click();
    await page.getByRole('button', { name: 'Remove Example tag' }).click();
    await submit();

    expect(submitted).not.toHaveBeenCalled();
    for (const key of ['required_positions', 'required_tags']) {
      await expect
        .element(field(key + '__error'))
        .toHaveTextContent('Please add at least one entry.');
    }
    expect(scroll.mock.contexts).toContain(await field('required_positions__error').findElement());

    scroll.mockRestore();
    await field('hide_required_lists').click();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0].hide_required_lists).toBe(true);
  });

  it('shows German list and selection errors together on reopening an empty draft', async () => {
    const language = vi.spyOn(navigator, 'language', 'get').mockReturnValue('de-DE');
    const { field, submitted, submit } = renderTaskForm(form010, {
      ...initialData,
      required_positions: [],
      required_tags: [],
      required_choice: null,
      confirm_review: false,
    });
    language.mockRestore();
    await submit();

    expect(submitted).not.toHaveBeenCalled();
    for (const key of ['required_positions', 'required_tags']) {
      await expect
        .element(field(key + '__error'))
        .toHaveTextContent('Bitte füge mindestens einen Eintrag hinzu.');
    }
    await expect
      .element(field('required_choice__error'))
      .toHaveTextContent('Bitte fülle dieses Feld aus.');
    await expect
      .element(field('confirm_review__error'))
      .toHaveTextContent('Bitte kreuze dieses Kästchen an.');
  });

  it('keeps a cleared confirmation invalid until it is ticked again', async () => {
    const { field, selectOption, submitted, submit } = renderTaskForm(form010, initialData);
    const input = await field('required_choice').findElement();
    input.focus();
    await userEvent.keyboard('{Backspace}');
    await field('confirm_review').click();
    await submit();

    await expect
      .element(field('required_choice__error'))
      .toHaveTextContent('Please fill in this field.');
    await expect
      .element(field('confirm_review__error'))
      .toHaveTextContent('Please tick this checkbox.');
    expect(submitted).not.toHaveBeenCalled();

    await selectOption('required_choice', 'Value a');
    await submit();
    expect(submitted).not.toHaveBeenCalled();
    await expect.element(field('confirm_review__error')).toBeVisible();
    await expect.element(field('required_choice__error')).not.toBeInTheDocument();

    await field('confirm_review').click();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0]).toMatchObject(initialData);
  });

  it('leaves a new required checkbox unchecked until the user confirms', async () => {
    // Isolate the confirmation from the manual workflow's pre-filled task data.
    const { field, submitted, submit } = renderTaskForm({
      jsonschema: {
        type: 'object',
        properties: { confirm_review: form010.jsonschema.properties.confirm_review },
        required: ['confirm_review'],
      },
      uischema: {
        'ui:layout': { Row_confirm_review: ['confirm_review'] },
        confirm_review: form010.uischema.confirm_review,
      },
    });
    await expect.element(field('confirm_review')).not.toBeChecked();
    await submit();
    expect(submitted).not.toHaveBeenCalled();

    await field('confirm_review').click();
    await submit();
    expect(submitted).toHaveBeenCalledOnce();
    expect(submitted.mock.calls[0][0].confirm_review).toBe(true);
  });
});
