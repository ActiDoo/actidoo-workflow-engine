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
 * Whether a value reads as null in a hide-if condition: anything blank, and an empty
 * list - a multi select with nothing chosen. The server reads them the same way. For
 * 'required' an empty list is not blank; a required list has its own minimum instead.
 */
export const readsAsNull = (value: unknown): boolean =>
  isBlank(value) || (Array.isArray(value) && value.length === 0);

/**
 * Paths of required fields that are present in the data but blank. AJV's `required` only
 * catches absent keys, so a whitespace-only text or a cleared select (null) would pass it.
 * A field with a hide-if keeps its 'required' as `ui:required` (see
 * changeRequiredDefinitionForFieldsWithHideIfDefinition); it counts while the field is shown.
 * Hidden fields are skipped: a hidden field is not required while it is not shown.
 */
export function collectBlankRequiredPaths(
  schema: RJSFSchema | undefined,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  formData: unknown,
  hiddenPaths: FormPath[]
): FormPath[] {
  const blank: FormPath[] = [];

  const walk = (levelSchema: any, levelUiSchema: any, levelData: any, path: FormPath): void => {
    if (!levelSchema?.properties || !levelData || typeof levelData !== 'object') return;
    const required: string[] = Array.isArray(levelSchema.required) ? levelSchema.required : [];

    for (const [key, property] of Object.entries<any>(levelSchema.properties)) {
      const fieldPath = [...path, key];
      if (isPathOnOrBelow(fieldPath, hiddenPaths)) continue;
      const value = levelData[key];
      const fieldUiSchema = levelUiSchema?.[key];
      const isRequired = required.includes(key) || fieldUiSchema?.['ui:required'] === true;

      // Absent keys are AJV's (rjsf hands over the data with every root key present, as
      // undefined); an object-typed field is an attachment, whose own type error says it all.
      if (isRequired && value !== undefined && property?.type !== 'object' && isBlank(value)) {
        blank.push(fieldPath);
        continue;
      }
      if (property?.items?.properties && Array.isArray(value)) {
        value.forEach((row, index) => {
          walk(property.items, fieldUiSchema?.items, row, [...fieldPath, index]);
        });
      } else if (property?.properties) {
        walk(property, fieldUiSchema, value, fieldPath);
      }
    }
  };

  walk(schema, uiSchema, formData, []);
  return blank;
}
