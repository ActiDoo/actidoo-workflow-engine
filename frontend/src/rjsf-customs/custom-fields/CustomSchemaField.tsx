// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement, useEffect, useMemo, useReducer, useRef } from 'react';
import _ from 'lodash';
import { evaluateHideIfAndFeel } from '@/services/FeelService';
import { getDefaultRegistry } from '@rjsf/core';
import { FieldProps } from '@rjsf/utils';

const OrgSchemaField = getDefaultRegistry().fields.SchemaField;

// Re-evaluating every hide-if and {{...}} description on each keystroke makes large
// forms feel sluggish, although typing rarely changes anything the conditions depend
// on. As a stopgap we evaluate at most once per window while changes arrive in quick
// succession, render the previous result in between, and always catch up right after
// the window. The clean solution (recompute only when a referenced field changed) is
// planned for the next release.
const HIDEIF_EVAL_WINDOW_MS = 300;

const CustomSchemaField = (props: FieldProps): ReactElement => {
  const { fieldPathId, formData, uiSchema, schema } = props as FieldProps & {
    fieldPathId?: { $id?: string; path?: unknown[] };
  };
  const formContext = (props.registry as any)?.formContext;

  // The cache is keyed on the formData identity alone: schema and uischema are fresh
  // clones on every render but derive deterministically from the task, while formData
  // is memoized upstream and only changes identity when the data really changed.
  const [, rerender] = useReducer((c: number) => c + 1, 0);
  const requestCatchUpEval = useMemo(
    () =>
      _.throttle(
        () => {
          rerender();
        },
        HIDEIF_EVAL_WINDOW_MS,
        { leading: false, trailing: true }
      ),
    []
  );
  useEffect(
    () => () => {
      requestCatchUpEval.cancel();
    },
    [requestCatchUpEval]
  );
  const evalCache = useRef<{
    formData: unknown;
    at: number;
    result: ReturnType<typeof evaluateHideIfAndFeel>;
  } | null>(null);

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

  if (isRoot) {
    // we calculate new properties only once, i.e. for the root SchemaField, but not for any child SchemaFields:

    // When changing code beware the difference between "props.formContext.formData" "and props.formData"!
    // Both are almost the same, but in case of dynamic list you will find in "props.formData" additionally
    // an array of the list elements, which shall be displayed initially.
    const cached = evalCache.current;
    const now = Date.now();
    let result;
    if (cached && cached.formData === formContext?.formData) {
      // Unchanged data (e.g. a scroll-induced re-render): nothing to evaluate.
      result = cached.result;
    } else if (cached && now - cached.at < HIDEIF_EVAL_WINDOW_MS) {
      // Mid-burst: show the previous result once more, catch up when the window ends.
      requestCatchUpEval();
      result = cached.result;
    } else {
      const orgFormData = {
        ...(formContext?.formData || {}),
      };
      result = evaluateHideIfAndFeel(orgFormData, effectiveUiSchema, schema);
      evalCache.current = { formData: formContext?.formData, at: now, result };
    }
    const { newUiSchema, newSchema } = result;

    const newProps = { ...props, uiSchema: newUiSchema, schema: newSchema };
    return <OrgSchemaField {...newProps} />;
  }

  return <OrgSchemaField {...{ ...props, uiSchema: effectiveUiSchema, schema }} />;
};

export default CustomSchemaField;
