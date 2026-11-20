// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement, useMemo } from 'react';
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
            title: ' ', // suppress id as label
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
      const widget = effectiveUiSchema?.['ui:widget'];
      const hideif = effectiveUiSchema?.['ui:hideif'];
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

  // Native validation runs before submit. Controls must reflect the current hide-if
  // values on the same render, including when the user immediately clicks Submit.
  const root = useMemo(
    () => (isRoot ? evaluateHideIfAndFeel(formContext?.formData, uiSchema, schema) : undefined),
    [isRoot, formContext?.formData, uiSchema, schema]
  );
  return (
    <OrgSchemaField
      {...props}
      uiSchema={root?.newUiSchema ?? effectiveUiSchema}
      schema={root?.newSchema ?? schema}
    />
  );
};

export default CustomSchemaField;
