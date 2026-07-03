// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

type JsonObject = Record<string, any>;

export const isObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const hasArrayType = (schema: JsonObject): boolean => {
  const type = schema.type;
  return type === 'array' || (Array.isArray(type) && type.includes('array'));
};

// The form transformation nests fields only via "properties" and "items"
// (itemgroups: array → items(object) → properties), so those are the only
// subschema carriers that need to be walked.
export const normalizeArrayDefaultsInJsonSchema = (schema: unknown): void => {
  if (!isObject(schema)) return;

  if (hasArrayType(schema) && !Object.prototype.hasOwnProperty.call(schema, 'default')) {
    schema.default = [];
  }

  Object.values(schema.properties ?? {}).forEach(normalizeArrayDefaultsInJsonSchema);
  normalizeArrayDefaultsInJsonSchema(schema.items);
};

// Itemgroups are recognizable by "ui:arrayAddButtonText", which only the backend's
// itemgroup transformation emits.
export const normalizeItemgroupCopyableInUiSchema = (uischema: unknown): void => {
  if (!isObject(uischema)) return;

  if (
    Object.prototype.hasOwnProperty.call(uischema, 'ui:arrayAddButtonText') &&
    !Object.prototype.hasOwnProperty.call(uischema, 'ui:copyable')
  ) {
    uischema['ui:copyable'] = true;
  }

  Object.values(uischema).forEach(normalizeItemgroupCopyableInUiSchema);
};
