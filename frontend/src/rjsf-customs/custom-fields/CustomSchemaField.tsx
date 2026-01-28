// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement } from 'react';
import { evaluateHideIfAndFeel } from '@/services/FeelService';
import { getDefaultRegistry } from '@rjsf/core';
import { FieldProps } from '@rjsf/utils';

const OrgSchemaField = getDefaultRegistry().fields.SchemaField;

const CustomSchemaField = (props: FieldProps): ReactElement => {
  const { fieldPathId, formData, uiSchema, schema } = props as FieldProps & {
    fieldPathId?: { $id?: string; path?: unknown[] };
  };
  const formContext = (props.registry as any)?.formContext;

  const effectiveUiSchema = 
  schema.type === 'null'
    ? {
        ...(uiSchema as any),
        'ui:options': {
          ...((uiSchema as any)?.['ui:options'] || {}),
          'title': ' ', //suppress id as label
        },
      }
    : uiSchema;

  // TODO the setTimeout's meaning is to asychronously start a job, which will do the props.onChange()
  // call later, so the rendering of this component will process until you hit the return-statement
  // BUT WHAT EXACTLY IS THE PURPOSE OF THESE ASYNC props.onChange() CALLS, UNDER WHICH CIRCUMSTANCES ETC?
  const fieldPath = fieldPathId?.path ?? [];
  if (formData === undefined) {
    if (schema.default !== undefined) {
      setTimeout(() => {
        props.onChange(schema.default, fieldPath);
      });
    } else if (schema.type === 'boolean') {
      // If a boolean is conditionally hidden/shown, RJSF may repeatedly drop it from formData.
      // Forcing a default here can then create an update/render loop.
      const widget = (effectiveUiSchema as any)?.['ui:widget'];
      const hideif = (effectiveUiSchema as any)?.['ui:hideif'];
      if (widget !== 'hidden' && hideif === undefined) {
        setTimeout(() => {
          props.onChange(false, fieldPath);
        });
      }
    }
  }

  const isRoot =
    fieldPathId?.$id === 'root' ||
    (Array.isArray(fieldPathId?.path) && fieldPathId?.path.length === 0) ||
    props.id === 'root';

  if (isRoot) {
    // we calculate new properties only once, i.e. for the root SchemaField, but not for any child SchemaFields:

    // When changing code beware the difference between "props.formContext.formData" "and props.formData"!
    // Both are almost the same, but in case of dynamic list you will find in "props.formData" additionally
    // an array of the list elements, which shall be displayed initially.
    const orgFormData = {
      ...(formContext?.formData || {}),
    };
    // console.log("**CustomSchemaField**")    
    // console.log("CustomSchemaField formContext", formContext) // {"numberA": {....}, "numberB": {...}, "Field_1aff9sg": {"ui:description": "Hello: {{ numberA * numberB }}"" }}
    // console.log("CustomSchemaField formData", formData)
    // console.log("CustomSchemaField uiSchema", uiSchema)
    // console.log("CustomSchemaField schema", schema)
    const { newUiSchema, newSchema } = evaluateHideIfAndFeel(orgFormData, effectiveUiSchema, schema);

    const newProps = { ...props, uiSchema: newUiSchema, schema: newSchema};
    return <OrgSchemaField {...newProps} />;
  }

  return <OrgSchemaField {...{ ...props, uiSchema: effectiveUiSchema, schema: schema }} />;
};

export default CustomSchemaField;
