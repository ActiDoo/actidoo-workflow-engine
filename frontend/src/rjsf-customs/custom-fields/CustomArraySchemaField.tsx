import React, { ReactElement } from 'react';
import { evaluateHideIfAndFeel } from '@/services/FeelService';
import { FieldProps } from '@rjsf/utils';
import CustomSchemaField from '@/rjsf-customs/custom-fields/CustomSchemaField';

const CustomArraySchemaField = (props: FieldProps): ReactElement => {
  const { formData, formContext, uiSchema, schema } = props;
  const evaluationFields = {
    ...formContext.formData,
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
