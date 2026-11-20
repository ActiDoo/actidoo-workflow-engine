// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { isAttachmentMultiSchema } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

/**
 * Whether rjsf must not pre-fill an array with `minItems` placeholder items.
 *
 * Conditional lists use defaultRepetitions for their initial rows. Filling them here
 * could create rows while the list is hidden. For multi-selects and attachments, a
 * placeholder would satisfy minItems without a selection or file.
 */
export const skipMinItemsPopulation = (schema: any): boolean => {
  if (schema?.hideif || isAttachmentMultiSchema(schema)) return true;
  const items = schema?.items;
  return (
    typeof items === 'object' && items !== null && !Array.isArray(items) && items.type !== 'object'
  );
};
