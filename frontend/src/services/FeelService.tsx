// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { RJSFSchema, UiSchema } from '@rjsf/utils';
import { evaluate, InterpreterContext, unaryTest } from 'feelin';
import _ from 'lodash';

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
 * - Hidden fields are treated as `undefined` (removed from context)
 *
 * The fixpoint iteration continues until the hidden map stabilizes or
 * max iterations are reached (prevents infinite loops).
 */
function computeHiddenMap(
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
    const ctx: Record<string, any> = { ...formData };

    // Remove all hidden fields from context (they should be treated as undefined)
    for (const k of uiKeys) {
      if (hiddenMap[k]) {
        delete ctx[k];
      }
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
        uiPropSchema && Object.hasOwn(uiPropSchema, pathElement)
          ? uiPropSchema[pathElement]
          : null;
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
  const hiddenMap = computeHiddenMap(uiSchema, schemaProperties, (orgFormData ?? {}) as Record<string, any>);

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
        const whole_incl_brackets = finding[0]; // e.g. "{{ numberA * numberB }}"
        const expression = finding[1]; // e.g. " numberA * numberB "
        try {
          let new_value = evaluate(expression, { ...orgFormData });
          if (new_value == null) {
            // if expression can not (yet) be evaluated, we do not want to render the expression,
            // but rather render an empty string
            new_value = '';
          } else if (typeof new_value === 'number') {
            // In Javascript we have precision problems: 11*(3*15.77) becomes 520.4100000000001
            // or 3*10.7 becomes 32.099999999999994 - lets format it properly.
            // TODO At the moment we only have Euro sums, but we might configure it in the future
            // and use cool stuff like:
            // num.toLocaleString("de-DE", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"USD"})
            new_value = new_value.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          }
          newUiSchema[fieldName]['ui:description'] = newUiSchema[fieldName]['ui:description'].replace(
            whole_incl_brackets,
            String(new_value)
          );
        } catch (e) {
          console.log(e);
        }
      }
    }

    // Search for 'hideif' and apply the pre-computed hidden state
    const hideif = fieldSchemaProps['ui:hideif'];
    const required = fieldSchemaProps['ui:required'];

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
    }
  }

  return { newUiSchema, newSchema, hide };
}
