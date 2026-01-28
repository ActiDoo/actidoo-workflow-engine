// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement } from 'react';
import { evaluateHideIfAndFeel } from '@/services/FeelService';
import { FieldProps } from '@rjsf/utils';
import CustomSchemaField from '@/rjsf-customs/custom-fields/CustomSchemaField';
const emptyobject = {};

const CustomArraySchemaField = (props: FieldProps): ReactElement => {
  const { formData, uiSchema, schema } = props;
  const formContext = (props.registry as any)?.formContext;
  const evaluationFields = {
    ...(formContext?.formData || emptyobject),
    ...formData,
  };

  if (uiSchema !== undefined) {
    const { newUiSchema, newSchema } = evaluateHideIfAndFeel(evaluationFields, uiSchema, schema);
    const newProps = { ...props, uiSchema: newUiSchema, schema: newSchema };
    return <CustomSchemaField {...newProps} />;
  }
  return <CustomSchemaField {...props} />;
};

export default CustomArraySchemaField;
