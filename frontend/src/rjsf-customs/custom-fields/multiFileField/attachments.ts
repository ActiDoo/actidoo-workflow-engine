// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

/**
 * Attachment data may contain placeholder entries like {} that look like files but are
 * none — rjsf creates them for required uploads, and old drafts still carry them.
 * Several places have to make the same call about them (the upload fields, the rjsf
 * form configuration, the draft normalization), so the definition lives here once.
 */

interface AttachmentFileLike {
  datauri?: string | null;
  filename?: string | null;
  hash?: string | null;
  id?: string | null;
  mimetype?: string | null;
}

export const isRealFile = (f: AttachmentFileLike | null | undefined): boolean =>
  // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- empty string means property not set, treat as falsy
  Boolean(f && (f.datauri || f.filename || f.hash || f.id || f.mimetype));

export const isAttachmentSingleSchema = (schema: any): boolean =>
  schema?.type === 'object' &&
  typeof schema.properties === 'object' &&
  !Array.isArray(schema.properties) &&
  (schema.properties?.datauri as { format?: string } | undefined)?.format === 'data-url';

// Deliberately keyed on the schema shape and not on the uischema marker ("ui:field":
// "AttachmentMulti"): rjsf's computeSkipPopulate hook only gets to see the JSON schema,
// and all users of this predicate must recognize exactly the same fields — so there is
// one definition that works everywhere.
export const isAttachmentMultiSchema = (schema: any): boolean =>
  schema?.type === 'array' &&
  typeof schema.items === 'object' &&
  !Array.isArray(schema.items) &&
  (schema.items.properties?.datauri as { format?: string } | undefined)?.format === 'data-url';
