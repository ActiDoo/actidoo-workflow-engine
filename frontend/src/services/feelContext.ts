// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { InterpreterContext } from 'feelin';
import type { RJSFSchema, UiSchema } from '@rjsf/utils';

// FEEL context helpers overview (example):
// Given root data { listA: [{ a: 1, listB: [{ b: 2 }] }], x: 5 } and id "root_listA_0_listB_0":
// - parseListSegments -> breaks "root_listA_0_listB_0" into [{ listA, 0 }, { listB, 0 }]
// - buildParentContext -> lets you use "parent" and "parent.parent" inside list items
// - buildThisContext -> adds "parent" to the current item (so "this.parent" works)
// - buildEvaluationContext -> merges root + current item + parent chain into one FEEL context
// - resolveHiddenFields/applyHiddenMask -> hides values by setting them to undefined
// - buildMaskedParentContext -> like buildParentContext, but it walks each list level,
//   applies hide-if masking per item, and then rebuilds the parent chain from those masked items

export type HideIfEvaluator = (expression: string, context: InterpreterContext | undefined) => boolean;

type ListSegment = {
  listName: string;
  index: number;
};

const ROOT_PREFIX = 'root_';
const trailingIndexPattern = /_(\d+)$/;
const segmentDelimiterPattern = /_(\d+)_/g;

function parseListSegments(id: string): ListSegment[] | null {
  // Parse RJSF id into list/index segments so we can reconstruct parent chains.
  // Example: "root_listA_0_listB_1_listC_2" -> [{listA,0},{listB,1},{listC,2}]
  if (!id.startsWith('root')) {
    return null;
  }

  let remaining = id;
  const reversed: ListSegment[] = [];

  while (remaining !== 'root') {
    const match = trailingIndexPattern.exec(remaining);
    if (!match) {
      return null;
    }

    const index = Number.parseInt(match[1], 10);
    const prefix = remaining.slice(0, match.index);
    const matches = [...prefix.matchAll(segmentDelimiterPattern)];

    if (matches.length > 0) {
      const lastMatch = matches[matches.length - 1];
      if (lastMatch.index === undefined) {
        return null;
      }

      const listName = prefix.slice(lastMatch.index + lastMatch[0].length);
      const parentPath = prefix.slice(0, lastMatch.index + lastMatch[0].length - 1);
      // Example step: "root_listA_0_listB" -> listName="listB", parentPath="root_listA_0"
      reversed.push({ listName, index });
      remaining = parentPath;
      continue;
    }

    if (!prefix.startsWith(ROOT_PREFIX)) {
      return null;
    }

    const listName = prefix.slice(ROOT_PREFIX.length);
    reversed.push({ listName, index });
    remaining = 'root';
  }

  return reversed.reverse();
}

function buildParentContext(rootData: any, id: string): any | undefined {
  // Build a parent chain (parent.parent...) for nested list items based on the RJSF id path.
  // Example: id "root_listA_0_listB_0_listC_0" yields parent=listB[0] with parent.parent=listA[0]
  const segments = parseListSegments(id);
  if (!segments || segments.length === 0) {
    return rootData;
  }

  if (segments.length === 1) {
    return rootData;
  }

  let current = rootData;
  const ancestors: any[] = [];

  for (let i = 0; i < segments.length - 1; i += 1) {
    const { listName, index } = segments[i];
    const list = current?.[listName];

    if (!Array.isArray(list) || list[index] === undefined) {
      return undefined;
    }

    const value = list[index];
    ancestors.push(value);
    current = value;
  }

  let parentContext: any = rootData;

  for (const ancestor of ancestors) {
    if (ancestor && typeof ancestor === 'object' && !Array.isArray(ancestor)) {
      // Wrap each ancestor so "parent.parent" walks up the chain.
      parentContext = { ...ancestor, parent: parentContext };
    } else {
      parentContext = ancestor;
    }
  }

  return parentContext;
}

function buildThisContext(formData: any, parentContext: any): any {
  // Create a "this" object that includes the parent chain for FEEL expressions.
  // Example: this = { ...currentItem, parent: <parentChain> } enables "this.parent".
  if (formData && typeof formData === 'object' && !Array.isArray(formData)) {
    return { ...formData, parent: parentContext };
  }

  return formData;
}

function applyHiddenMask(
  orgFormData: InterpreterContext | undefined,
  hiddenFields: Set<string>
): InterpreterContext | undefined {
  if (!orgFormData || typeof orgFormData !== 'object') {
    return orgFormData;
  }

  // "Mask" means we keep the object but overwrite hidden fields with undefined
  // so FEEL evaluations treat them as not present while preserving other values.
  const masked: InterpreterContext = { ...orgFormData };
  for (const field of hiddenFields) {
    masked[field] = undefined;
  }

  const thisContext = masked.this;
  if (thisContext && typeof thisContext === 'object' && !Array.isArray(thisContext)) {
    // Mirror masked fields into "this" so hide-if in list items behaves the same as root context.
    masked.this = { ...thisContext };
    for (const field of hiddenFields) {
      (masked.this as InterpreterContext)[field] = undefined;
    }
  }

  return masked;
}

export function buildEvaluationContext(
  maskedRootContext: InterpreterContext | undefined,
  itemData: any,
  parentContext: InterpreterContext | undefined
): InterpreterContext {
  // Assemble the FEEL evaluation context with root data, current item, and parent chain.
  const thisContext = buildThisContext(itemData, parentContext);
  return {
    ...(maskedRootContext ?? {}),
    ...(itemData ?? {}),
    this: thisContext,
    parent: parentContext,
  };
}

export function buildMaskedParentContext(
  rootData: InterpreterContext | undefined,
  rootUiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  id: string,
  maskedRootContext: InterpreterContext | undefined,
  evaluateHideIf: HideIfEvaluator
): InterpreterContext | undefined {
  // Rebuild the parent chain with per-level hide-if masking so parent access respects hidden fields.
  const segments = parseListSegments(id);
  if (!segments || segments.length === 0) {
    return maskedRootContext ?? rootData;
  }

  if (segments.length === 1) {
    return maskedRootContext ?? rootData;
  }

  if (!rootUiSchema) {
    return buildParentContext(maskedRootContext ?? rootData, id);
  }

  // Walk the list path and rebuild the parent chain with masked item data per level.
  let parentContext: InterpreterContext | undefined = maskedRootContext ?? rootData;
  let dataCursor: any = rootData;
  let uiSchemaCursor: any = rootUiSchema;

  for (let i = 0; i < segments.length - 1; i += 1) {
    const { listName, index } = segments[i];
    const listData = dataCursor?.[listName];
    const itemData = Array.isArray(listData) ? listData[index] : undefined;
    const itemUiSchema = uiSchemaCursor?.[listName]?.items;

    // If schema/data don't align, fall back to the original parent resolution.
    if (itemData === undefined || !itemUiSchema) {
      return buildParentContext(maskedRootContext ?? rootData, id);
    }

    const evalContext = buildEvaluationContext(maskedRootContext, itemData, parentContext);

    // Mask item fields based on its own hide-if rules before it becomes part of the parent chain.
    const { hiddenFields } = resolveHiddenFields(itemUiSchema, evalContext, evaluateHideIf);
    const maskedItem = applyHiddenMask(itemData, hiddenFields);

    if (maskedItem && typeof maskedItem === 'object' && !Array.isArray(maskedItem)) {
      parentContext = { ...maskedItem, parent: parentContext };
    } else {
      parentContext = maskedItem;
    }

    dataCursor = itemData;
    uiSchemaCursor = itemUiSchema;
  }

  return parentContext;
}

export function resolveHiddenFields(
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  orgFormData: InterpreterContext | undefined,
  evaluateHideIf: HideIfEvaluator
): { hiddenFields: Set<string>; maskedContext: InterpreterContext | undefined } {
  // Resolve all fields that must be hidden and return a "masked" context
  // where those fields are set to undefined for consistent FEEL evaluation.
  const hiddenFields = new Set<string>();

  if (!uiSchema) {
    return { hiddenFields, maskedContext: orgFormData };
  }

  let currentHidden = hiddenFields;

  // Iterate to a fixpoint because hide-if chains can depend on previously hidden fields.
  for (let pass = 0; pass < 10; pass += 1) {
    const maskedContext = applyHiddenMask(orgFormData, currentHidden);
    const nextHidden = new Set<string>();

    for (const fieldName of Object.keys(uiSchema ?? {})) {
      const fieldSchemaProps = uiSchema[fieldName];
      const hideif = fieldSchemaProps?.['ui:hideif'];

      if (hideif !== undefined) {
        const hide = evaluateHideIf(hideif.slice(1), maskedContext);
        if (hide) {
          nextHidden.add(fieldName);
        }
      }
    }

    // Stop once the hidden set stabilizes to avoid unnecessary passes.
    if (nextHidden.size === currentHidden.size && [...nextHidden].every(x => currentHidden.has(x))) {
      return { hiddenFields: nextHidden, maskedContext };
    }

    currentHidden = nextHidden;
  }

  // Guardrail: return the best-effort mask after max passes.
  return { hiddenFields: currentHidden, maskedContext: applyHiddenMask(orgFormData, currentHidden) };
}
