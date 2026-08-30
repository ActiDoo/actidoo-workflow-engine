// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { RJSFSchema, UiSchema } from '@rjsf/utils';

import { type FormPath, isPathOnOrBelow } from '@/services/FeelService';

/**
 * Whether a submitted value carries no value: nothing, null, or a string that is empty or
 * whitespace only. Booleans, numbers, lists and objects always count as a value - `false`,
 * `0` and `[]` are values. The server applies the same rule to submissions.
 */
export const isBlank = (value: unknown): boolean =>
  value === undefined || value === null || (typeof value === 'string' && value.trim() === '');

/**
 * Paths of required fields that are present in the data but blank. AJV's `required` only
 * catches absent keys, so a whitespace-only text or a cleared select (null) would pass it.
 * Hidden fields are skipped: a hidden field is not required while it is not shown.
 */
export function collectBlankRequiredPaths(
  schema: RJSFSchema | undefined,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  formData: unknown,
  hiddenPaths: FormPath[]
): FormPath[] {
  const blank: FormPath[] = [];

  const walk = (levelSchema: any, levelData: any, path: FormPath): void => {
    if (!levelSchema?.properties || !levelData || typeof levelData !== 'object') return;
    const required: string[] = Array.isArray(levelSchema.required) ? levelSchema.required : [];

    for (const [key, property] of Object.entries<any>(levelSchema.properties)) {
      const fieldPath = [...path, key];
      if (isPathOnOrBelow(fieldPath, hiddenPaths)) continue;
      const value = levelData[key];

      // Absent keys are AJV's (rjsf hands over the data with every root key present, as
      // undefined); an object-typed field is an attachment, whose own type error says it all.
      if (
        required.includes(key) &&
        value !== undefined &&
        property?.type !== 'object' &&
        isBlank(value)
      ) {
        blank.push(fieldPath);
        continue;
      }
      if (property?.items?.properties && Array.isArray(value)) {
        value.forEach((row, index) => {
          walk(property.items, row, [...fieldPath, index]);
        });
      } else if (property?.properties) {
        walk(property, value, fieldPath);
      }
    }
  };

  walk(schema, formData, []);
  return blank;
}
