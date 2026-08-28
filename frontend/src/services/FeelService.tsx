// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { RJSFSchema, UiSchema } from '@rjsf/utils';
import { evaluate, InterpreterContext, unaryTest } from 'feelin';
import _ from 'lodash';

import {
  applyHiddenMask,
  buildEvaluationContext,
  HideIfEvaluator,
  resolveHiddenFields,
} from '@/services/feelContext';

// ============================================================================
// Internal Helpers
// ============================================================================

function isBooleanSchema(schema: any): boolean {
  const t = schema?.type;
  return Array.isArray(t) ? t.includes('boolean') : t === 'boolean';
}

/**
 * Safely evaluates a FEEL unary test expression.
 * Strips the leading '=' if present (FEEL expression marker).
 * Returns false on any evaluation error.
 */
function safeUnaryTest(expr: string, ctx: Record<string, any>): boolean {
  try {
    const trimmed = expr.trim();
    const normalized = trimmed.startsWith('=') ? trimmed.slice(1) : trimmed;
    return unaryTest(normalized, { ...ctx });
  } catch {
    return false;
  }
}

/**
 * Computes which fields are hidden via ui:hideif using fixpoint iteration.
 *
 * This is necessary because hideif expressions can reference boolean fields,
 * and those boolean fields might themselves be conditionally hidden.
 *
 * Semantics:
 * - Visible-but-missing booleans are treated as `false` in the evaluation context
 * - Hidden fields are removed from the context, so FEEL sees them as null - both as bare
 *   names and inside `this`, the row's own data in a list item
 *
 * The fixpoint iteration continues until the hidden map stabilizes or
 * max iterations are reached (prevents infinite loops).
 */
export function computeHiddenMap(
  uiSchema: UiSchema<any, RJSFSchema, any>,
  schemaProperties: Record<string, any> | undefined,
  formData: Record<string, any>
): Record<string, boolean> {
  const uiKeys = Object.keys(uiSchema);
  const booleanKeys = schemaProperties
    ? Object.keys(schemaProperties).filter(k => isBooleanSchema(schemaProperties[k]))
    : [];

  // Initialize all fields as not hidden
  let hiddenMap: Record<string, boolean> = {};
  for (const k of uiKeys) hiddenMap[k] = false;

  // Iterate until fixpoint is reached
  const maxIterations = Math.max(1, uiKeys.length + 2);
  for (let iter = 0; iter < maxIterations; iter++) {
    // Build context excluding hidden fields (they should be treated as null)
    const hiddenKeys = new Set(uiKeys.filter(k => hiddenMap[k]));
    const ctx: Record<string, any> = Object.fromEntries(
      Object.entries(formData).filter(([k]) => !hiddenKeys.has(k))
    );
    if (ctx.this && typeof ctx.this === 'object' && !Array.isArray(ctx.this)) {
      ctx.this = Object.fromEntries(Object.entries(ctx.this).filter(([k]) => !hiddenKeys.has(k)));
    }

    // Visible-but-missing booleans default to false
    for (const k of booleanKeys) {
      if (ctx[k] === undefined) {
        ctx[k] = false;
      }
    }

    const nextHiddenMap: Record<string, boolean> = { ...hiddenMap };
    for (const fieldName of uiKeys) {
      const hideif = (uiSchema as any)[fieldName]?.['ui:hideif'];
      if (typeof hideif === 'string') {
        nextHiddenMap[fieldName] = safeUnaryTest(hideif, ctx);
      }
    }

    // Check if we've reached a fixpoint
    if (_.isEqual(nextHiddenMap, hiddenMap)) break;
    hiddenMap = nextHiddenMap;
  }

  return hiddenMap;
}

// ============================================================================
// Exported Functions
// ============================================================================

/**
 * Moves 'required' from JSON schema to UI schema for fields with hideif.
 *
 * Im Frontend Validation-Schema dürfen wir die versteckten Felder nicht als required setzen.
 * Wir werden deshalb die "required" Eigenschaft vorerst aus dem jsonschema in das uischema schieben.
 * Später, in einer Kopie des Schemas für das Rendern, wird die Eigenschaft wieder zurückgeschoben.
 * Die Required-Eigenschaft wird also nur durch die HTML5-Validierung sichergestellt.
 */
export function changeRequiredDefinitionForFieldsWithHideIfDefinition(
  schema: any,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined
): void {
  if (!schema.properties || !uiSchema) return;

  const queue: string[][] = Object.keys(schema.properties).map(x => [x]);
  let propPath: string[] | undefined;

  while ((propPath = queue.shift())) {
    // traverse schema
    let parentProp;
    let curProp = schema;
    const propPathQueue = [...propPath];
    let pathElement;
    let uiPropSchema: any = uiSchema;

    while ((pathElement = propPathQueue.shift())) {
      if ((curProp?.type ?? '') === 'array' && curProp.items) {
        curProp = curProp.items;
        uiPropSchema = uiPropSchema?.items;
      }
      parentProp = curProp;
      curProp = curProp.properties?.[pathElement];
      uiPropSchema =
        uiPropSchema && Object.hasOwn(uiPropSchema, pathElement) ? uiPropSchema[pathElement] : null;
    }

    if ((curProp?.type ?? '') === 'array' && curProp?.items?.properties) {
      for (const subProp of Object.keys(curProp.items.properties)) {
        queue.push([...propPath, subProp]);
      }
    }

    const hideif = uiPropSchema?.['ui:hideif'];
    if (
      hideif !== undefined &&
      Array.isArray(parentProp.required) &&
      parentProp.required.includes(propPath[propPath.length - 1])
    ) {
      uiPropSchema['ui:required'] = true;
      _.remove(parentProp.required, x => propPath && x === propPath[propPath.length - 1]);
    }

    // An array expresses 'required' as minItems, so the same applies to a hidden dynamic list
    // or attachment field: it must not block the submit while it is not shown. Moved back by
    // evaluateHideIfAndFeel as soon as the field becomes visible again.
    if (hideif !== undefined && typeof curProp?.minItems === 'number') {
      uiPropSchema['ui:minItems'] = curProp.minItems;
      delete curProp.minItems;
    }
  }
}

/**
 * Evaluates ui:hideif conditions and FEEL expressions in ui:description.
 *
 * For hideif: Uses fixpoint iteration to correctly handle interdependent boolean fields.
 * For FEEL: Replaces {{ expression }} patterns in descriptions with evaluated values.
 */
export function evaluateHideIfAndFeel(
  orgFormData: InterpreterContext | undefined,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  schema: RJSFSchema
): {
  newUiSchema: UiSchema<any, RJSFSchema, any> | undefined;
  newSchema: RJSFSchema;
  hide: boolean;
} {
  if (!uiSchema) {
    return { newUiSchema: uiSchema, newSchema: schema, hide: false };
  }

  const newUiSchema = _.cloneDeep(uiSchema);
  const newSchema = _.cloneDeep(schema);
  const schemaProperties = (schema as any)?.properties as Record<string, any> | undefined;
  const hiddenMap = computeHiddenMap(
    uiSchema,
    schemaProperties,
    (orgFormData ?? {}) as Record<string, any>
  );

  let hide = false;

  for (const fieldName of Object.keys(uiSchema)) {
    const fieldSchemaProps = uiSchema[fieldName];

    // Search for FEEL expressions in ui:description
    // e.g. "The product is {{ numberA * numberB }}."
    const description: string = fieldSchemaProps['ui:description'];
    if (description) {
      const regexp = /{{(.*?)}}/g;
      const findings = [...description.matchAll(regexp)]; // description can be undefined, then create an empty array

      for (const finding of findings) {
        const wholeInclBrackets = finding[0]; // e.g. "{{ numberA * numberB }}"
        const expression = finding[1]; // e.g. " numberA * numberB "
        try {
          let newValue = evaluate(expression, { ...orgFormData });
          if (newValue == null) {
            // if expression can not (yet) be evaluated, we do not want to render the expression,
            // but rather render an empty string
            newValue = '';
          } else if (typeof newValue === 'number') {
            // In Javascript we have precision problems: 11*(3*15.77) becomes 520.4100000000001
            // or 3*10.7 becomes 32.099999999999994 - lets format it properly.
            // TODO At the moment we only have Euro sums, but we might configure it in the future
            // and use cool stuff like:
            // num.toLocaleString("de-DE", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"USD"})
            newValue = newValue.toLocaleString('de-DE', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            });
          }
          newUiSchema[fieldName]['ui:description'] = newUiSchema[fieldName][
            'ui:description'
          ].replace(wholeInclBrackets, String(newValue));
        } catch (e) {
          console.log(e);
        }
      }
    }

    // Search for 'hideif' and apply the pre-computed hidden state
    const hideif = fieldSchemaProps['ui:hideif'];
    const required = fieldSchemaProps['ui:required'];
    const minItems = fieldSchemaProps['ui:minItems'];

    if (hideif !== undefined) {
      hide = Boolean(hiddenMap[fieldName]);

      if (hide) {
        newUiSchema[fieldName]['ui:widget'] = 'hidden';
      } else if (newUiSchema[fieldName]?.['ui:widget'] === 'hidden') {
        // Unhide if it was hidden by a previous hide-if evaluation
        delete newUiSchema[fieldName]['ui:widget'];
      }

      if (!hide && required) {
        if (!newSchema.required) {
          newSchema.required = [];
        }
        if (!newSchema.required.includes(fieldName)) {
          newSchema.required.push(fieldName);
        }
      }

      // Counterpart of the minItems move in changeRequiredDefinitionForFieldsWithHideIfDefinition:
      // a visible list validates (and renders its initial rows) with its minItems again.
      const fieldSchema = (newSchema as any)?.properties?.[fieldName];
      if (!hide && typeof minItems === 'number' && fieldSchema) {
        fieldSchema.minItems = minItems;
      }
    }
  }

  return { newUiSchema, newSchema, hide };
}

// ============================================================================
// Hidden paths - what the form currently does not show
// ============================================================================

/** A path into the form data: property names, list indexes for rows. */
export type FormPath = Array<string | number>;

const evaluateHideIfForMasking: HideIfEvaluator = (expression, context) => {
  try {
    return unaryTest(expression, { ...(context ?? {}) });
  } catch {
    return false;
  }
};

/**
 * Collects the paths of every field the form currently hides.
 *
 * Each level is evaluated the way it is rendered: root fields against the form data
 * (as the root SchemaField does), list rows against the context CustomArraySchemaField
 * builds for them - the root data with its hidden fields masked, the row itself as `this`,
 * the enclosing rows as the `parent` chain. A hidden field ends the descent: whatever
 * lies below it is hidden with it and needs no path of its own.
 */
export function collectHiddenPaths(
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  schema: RJSFSchema | undefined,
  formData: unknown
): FormPath[] {
  const hiddenPaths: FormPath[] = [];
  if (!uiSchema || !schema) {
    return hiddenPaths;
  }

  const rootData: Record<string, any> =
    formData && typeof formData === 'object' && !Array.isArray(formData)
      ? (formData as Record<string, any>)
      : {};
  const maskedRoot =
    resolveHiddenFields(uiSchema, rootData, evaluateHideIfForMasking).maskedContext ?? rootData;

  const walk = (
    levelUiSchema: Record<string, any>,
    levelSchema: Record<string, any>,
    levelData: Record<string, any>,
    path: FormPath,
    evaluationContext: Record<string, any>,
    parentContext: InterpreterContext | undefined
  ): void => {
    const properties: Record<string, any> = levelSchema?.properties ?? {};
    const hiddenMap = computeHiddenMap(levelUiSchema, properties, evaluationContext);

    for (const key of Object.keys(levelUiSchema)) {
      if (key.startsWith('ui:')) continue;
      if (hiddenMap[key]) {
        hiddenPaths.push([...path, key]);
        continue;
      }

      // Descend into the rows of a visible dynamic list.
      const itemUiSchema = levelUiSchema[key]?.items;
      const itemSchema = properties[key]?.items;
      const rows = levelData?.[key];
      if (!itemUiSchema || !itemSchema?.properties || !Array.isArray(rows)) continue;

      rows.forEach((row, index) => {
        if (!row || typeof row !== 'object' || Array.isArray(row)) return;
        const rowContext = buildEvaluationContext(maskedRoot, row, parentContext);
        const { hiddenFields } = resolveHiddenFields(
          itemUiSchema,
          rowContext,
          evaluateHideIfForMasking
        );
        const maskedRow = applyHiddenMask(row, hiddenFields) ?? row;
        walk(itemUiSchema, itemSchema, row, [...path, key, index], rowContext, {
          ...maskedRow,
          parent: parentContext,
        });
      });
    }
  };

  walk(uiSchema, schema, rootData, [], rootData, maskedRoot);
  return hiddenPaths;
}

/** Whether an rjsf error `property` ("root_key", ".list.0.key" ...) lies on or below one of the paths. */
export function isOnOrBelowPath(property: string | undefined, paths: FormPath[]): boolean {
  if (!property) {
    return false;
  }
  // rjsf writes the AJV instance path with dots; a required error on the root level
  // has no leading dot, one inside the data has.
  const segments = property.replace(/^\./, '').split('.');
  return paths.some(
    path =>
      path.length <= segments.length && path.every((segment, i) => String(segment) === segments[i])
  );
}

/**
 * Drops validation errors of fields the form does not show. Mirrors what the backend does
 * with the submitted data: a hidden field, and everything below it, is treated as absent,
 * so an empty required field in a hidden list row must not block the submission. Errors of
 * visible fields pass through untouched.
 */
export function dropErrorsOfHiddenFields<T extends { property?: string }>(
  errors: T[],
  hiddenPaths: FormPath[]
): T[] {
  if (hiddenPaths.length === 0) {
    return errors;
  }
  return errors.filter(error => !isOnOrBelowPath(error.property, hiddenPaths));
}
