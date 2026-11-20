// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import get from 'lodash/get';
import type { ErrorSchema, FieldPathList, FieldValidation, FormValidation } from '@rjsf/utils';
import type { useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];
type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
const fieldSelector = '[data-form-field-path]';

// An invalid submit fires one non-bubbling event per control, then skips the submit handler.
// Run the same RJSF validation once, after all those events. validateForm never submits.
export function validateOnInvalid(form: HTMLFormElement, validate: () => void): () => void {
  let frame: number | undefined;
  const onInvalid = (event: Event) => {
    if (event.target instanceof Element && event.target.closest(fieldSelector))
      event.preventDefault();
    if (frame === undefined) {
      frame = requestAnimationFrame(() => {
        frame = undefined;
        validate();
      });
    }
  };
  form.addEventListener('invalid', onInvalid, true);
  return () => {
    form.removeEventListener('invalid', onInvalid, true);
    if (frame !== undefined) cancelAnimationFrame(frame);
  };
}

function nativeMessage(control: Control, t: Translate): string {
  const validity = control.validity;
  if (validity.badInput)
    return t(control.type === 'number' ? 'formErrors.badNumber' : 'formErrors.badInput');
  if (validity.valueMissing)
    return t(control.type === 'checkbox' ? 'formErrors.checkboxRequired' : 'formErrors.required');
  if (control instanceof HTMLInputElement) {
    if (validity.rangeUnderflow) return t('formErrors.minimum', { limit: control.min });
    if (validity.rangeOverflow) return t('formErrors.maximum', { limit: control.max });
  }
  return control.validationMessage;
}

export function addNativeErrors(
  form: HTMLFormElement | undefined,
  errors: FormValidation,
  schemaErrors: ErrorSchema | undefined,
  t: Translate
): void {
  if (!form || form.noValidate) return;
  for (const control of form.querySelectorAll<Control>(
    'input:invalid,select:invalid,textarea:invalid'
  )) {
    // Composite widgets can use an anonymous input for HTML validation. The enclosing
    // RJSF field supplies its exact path, including row indices and names with underscores.
    const field = control.closest<HTMLElement>(fieldSelector);
    if (!field?.dataset.formFieldPath) continue;
    const path: FieldPathList = JSON.parse(field.dataset.formFieldPath);
    const handler: FieldValidation | undefined = get(errors, path);
    if (!handler) continue;
    const existing = [...(get(schemaErrors, path)?.__errors ?? []), ...(handler.__errors ?? [])];
    // An empty select can already have a more specific required/minItems message.
    if (control.validity.valueMissing && !control.validity.badInput && existing.length) continue;
    const message = nativeMessage(control, t);
    if (!existing.includes(message)) handler.addError(message);
  }
}

export function focusFirstError(form: HTMLFormElement | undefined): void {
  const message = form?.querySelector<HTMLElement>('[id$="__error"]');
  if (!message) return;
  const field = message.closest(fieldSelector);
  const control = field?.querySelector<HTMLElement>(
    'input:not([type="hidden"]):not(:disabled):not([tabindex="-1"]), select:not(:disabled), textarea:not(:disabled), button:not(:disabled), ui5-button:not([disabled]), [tabindex="0"]:not(:disabled)'
  );
  (control ?? message).focus({ preventScroll: true });
  message.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
}
