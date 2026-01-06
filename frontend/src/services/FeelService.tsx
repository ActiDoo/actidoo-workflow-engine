// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { RJSFSchema, UiSchema } from '@rjsf/utils';
import { log } from 'console';
import { evaluate, InterpreterContext, unaryTest } from 'feelin';
import _ from 'lodash';

export function changeRequiredDefinitionForFieldsWithHideIfDefinition(
  schema: any,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined
): void {
  // Im Frontend Validation-Schema dürfen wir die versteckten Felder nicht als required setzen.
  // Wir werden deshalb die "required" Eigenschaft vorerst aus dem jsonschema in das uischema schieben.
  // Später, in einer Kopie des Schemas für das Rendern, wird die Eigenschaft wieder zurückgeschoben.
  // Die Required-Eigenschaft wird also nur durch die HTML5-Validierung sichergestellt.
  if (schema.properties && uiSchema !== undefined) {
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

      if ((curProp?.type ?? '') === 'array' && curProp?.items && curProp?.items?.properties) {
        for (const subProp of Object.keys(curProp?.items?.properties)) {
          queue.push([...propPath, subProp]);
        }
      }

      const hideif = uiPropSchema ? uiPropSchema['ui:hideif'] : undefined;
      if (
        hideif !== undefined &&
        Array.isArray(parentProp.required) &&
        parentProp.required.indexOf(propPath[propPath.length - 1]) !== -1
      ) {
        uiPropSchema['ui:required'] = true;
        _.remove(parentProp.required, x => propPath && x === propPath[propPath.length - 1]);
      }
    }
  }
}

export const evaluateHideIfAndFeel = function (
  orgFormData: InterpreterContext | undefined,
  uiSchema: UiSchema<any, RJSFSchema, any> | undefined,
  schema: RJSFSchema
): {
  newUiSchema: UiSchema<any, RJSFSchema, any> | undefined;
  newSchema: RJSFSchema;  
  hide: boolean;
} {
  let newUiSchema = uiSchema;
  let newSchema = schema;
  let hide: boolean = false;

  if (uiSchema !== undefined) {
    newUiSchema = _.cloneDeep(uiSchema);
    newSchema = _.cloneDeep(schema);

    for (const fieldName of Object.keys(uiSchema ?? {})) {
      const fieldSchemaProps = uiSchema[fieldName];
      
      //search for a FEEL expression
      const des: string = fieldSchemaProps['ui:description']; //e.g. "The product is {{ numberA * numberB }}."
      const regexp = /{{(.*?)}}/g;
      const findings = des ? [...des.matchAll(regexp)] : [] //des can be undefined, then create an empty array
      for (const finding of findings) {
        const whole_incl_brackets = finding[0] //e.g. "{{ numberA * numberB }}"
        const expression = finding[1] // e.g. " numberA * numberB "
        //console.log("whole_incl_brackets", whole_incl_brackets)
        //console.log("expression", expression)
        try {
          let new_value = evaluate(expression, {...orgFormData})
          if (new_value == null) {
            new_value = "" // if expression can not (yet) be evaluated, we do not want to render the expression, but rather render an empty string
          }
          console.log("replace " + newUiSchema[fieldName]["ui:description"] + " with " + new_value)
          if (typeof new_value == "number") {
            // in Javascript we have precision problems: 11*(3*15.77) becomes 520.4100000000001 or 3*10.7 becomes 32.099999999999994
            // lets format it properly:
            // TODO At the moment we only have Euro sums, but we might configure it in the future and use cool stuff like
            // num.toLocaleString("de-DE", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"EUR"})
            // num.toLocaleString("en-US", {style:"currency", currency:"USD"})
            new_value = new_value.toLocaleString("de-DE",  {minimumFractionDigits: 2, maximumFractionDigits: 2})
          }
          newUiSchema[fieldName]["ui:description"] = newUiSchema[fieldName]["ui:description"].replace(whole_incl_brackets, String(new_value))
          
        } catch (e) {
          console.log(e)
        }
      }
      
      //search for 'hideif'
      const hideif = fieldSchemaProps['ui:hideif'];
      const required = fieldSchemaProps['ui:required'];
      if (hideif !== undefined) {
        hide = unaryTest(hideif.slice(1), { ...orgFormData });
        if (hide) {
          newUiSchema[fieldName]['ui:widget'] = 'hidden';
        } else if (required) {
          if (!newSchema.required) {
            newSchema.required = [];
          }
          newSchema.required.push(fieldName);
        }
      }
    }
  }
  return { newUiSchema, newSchema, hide };
};
