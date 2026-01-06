// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { Form } from '@rjsf/react-bootstrap';
import { customizeValidator } from '@rjsf/validator-ajv8';
import type { RegistryFieldsType, RegistryWidgetsType } from '@rjsf/utils';

import './TaskForm.scss';

import CustomNullField from '@/rjsf-customs/custom-fields/CustomNullField';
import { CustomObjectFieldTemplate } from '@/rjsf-customs/templates/ObjectFieldTemplate';
import CustomArrayFieldItemTemplate from '@/rjsf-customs/templates/ArrayFieldItemTemplate';
import CustomArrayFieldTemplate from '@/rjsf-customs/templates/ArrayFieldTemplate';
import CustomComboBox from '@/rjsf-customs/custom-widgets/CustomComboBox';
import CustomSchemaField from '@/rjsf-customs/custom-fields/CustomSchemaField';
import CustomArraySchemaField from '@/rjsf-customs/custom-fields/CustomArraySchemaField';
import CustomMultiFileField from '@/rjsf-customs/custom-fields/multiFileField/CustomMultiFileField';
import CustomSingleFileField from '@/rjsf-customs/custom-fields/multiFileField/CustomSingleFileField';
import CustomSelect from '@/rjsf-customs/custom-widgets/CustomSelect';
import CustomCheckbox from '@/rjsf-customs/custom-widgets/CustomCheckbox';
import CustomFieldErrorTemplate from '@/rjsf-customs/templates/CustomFieldErrorTemplate';
import MultiSelectDynamic from '@/rjsf-customs/custom-widgets/MultiSelectDynamic';
import MultiSelectStatic from '@/rjsf-customs/custom-widgets/MultiSelectStatic';
import SelectDynamic from '@/rjsf-customs/custom-widgets/SelectDynamic';
import SelectStatic from '@/rjsf-customs/custom-widgets/SelectStatic';

const validator = customizeValidator();

const customFields: RegistryFieldsType = {
  AttachmentMulti: CustomMultiFileField,
  AttachmentSingle: CustomSingleFileField,
  NullField: CustomNullField,
  ArraySchemaField: CustomArraySchemaField,
  SchemaField: CustomSchemaField,
};

const customWidgets: RegistryWidgetsType = {
  combobox: CustomComboBox,
  SelectWidget: CustomSelect,
  CheckboxWidget: CustomCheckbox,
  MultiSelectDynamic,
  MultiSelectStatic,
  SelectDynamic,
  SelectStatic,
};

const customTemplates = {
  ObjectFieldTemplate: CustomObjectFieldTemplate,
  ArrayFieldTemplate: CustomArrayFieldTemplate,
  ArrayFieldItemTemplate: CustomArrayFieldItemTemplate,
  FieldErrorTemplate: CustomFieldErrorTemplate,
};

type BaseFormProps = React.ComponentProps<typeof Form>;

export type TaskFormProps = Omit<BaseFormProps, 'validator'> & {
  validator?: BaseFormProps['validator'];
};

const TaskForm: React.FC<TaskFormProps> = ({
  validator: providedValidator,
  templates,
  fields,
  widgets,
  showErrorList,
  children,
  ...rest
}) => (
  <Form
    {...rest}
    validator={providedValidator ?? validator}
    templates={templates ?? customTemplates}
    fields={fields ?? customFields}
    widgets={widgets ?? customWidgets}
    showErrorList={showErrorList ?? false}>
    {children ?? <></>}
  </Form>
);

export { validator as taskFormValidator, customFields, customWidgets, customTemplates };
export default TaskForm;
