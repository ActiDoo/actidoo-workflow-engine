// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { isAttachmentMultiSchema } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

/**
 * Whether rjsf must not pre-fill an array with `minItems` placeholder items.
 *
 * Dynamic lists (arrays of objects) get their initial rows that way. Arrays of scalars -
 * a required multi-select - and attachment lists must stay empty: a placeholder item would
 * satisfy `minItems` without being a selection or a file.
 */
export const skipMinItemsPopulation = (schema: any): boolean => {
  if (isAttachmentMultiSchema(schema)) return true;
  const items = schema?.items;
  return (
    typeof items === 'object' && items !== null && !Array.isArray(items) && items.type !== 'object'
  );
};
