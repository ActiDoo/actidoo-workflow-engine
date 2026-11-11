// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { RJSFValidationError, UiSchema } from '@rjsf/utils';

export const PATTERN_MESSAGE_KEY = 'ui:patternMessage';

export function patternMessageForProperty(
  uiSchema: UiSchema | undefined,
  property: string | undefined
): string | undefined {
  if (!uiSchema || !property) {
    return undefined;
  }
  let node: unknown = uiSchema;
  for (const segment of property.replace(/^\./, '').split('.')) {
    if (!node || typeof node !== 'object') {
      return undefined;
    }
    const record = node as Record<string, unknown>;
    node = /^\d+$/.test(segment) ? record.items : record[segment];
  }
  if (!node || typeof node !== 'object') {
    return undefined;
  }
  const message = (node as Record<string, unknown>)[PATTERN_MESSAGE_KEY];
  return typeof message === 'string' && message ? message : undefined;
}

export function replacePatternErrorMessages(
  errors: RJSFValidationError[],
  uiSchema: UiSchema | undefined,
  fallback: string
): RJSFValidationError[] {
  return errors.map(error => {
    if (error.name !== 'pattern') {
      return error;
    }
    const message = patternMessageForProperty(uiSchema, error.property) ?? fallback;
    return { ...error, message, stack: `${error.property ?? ''} ${message}`.trim() };
  });
}
