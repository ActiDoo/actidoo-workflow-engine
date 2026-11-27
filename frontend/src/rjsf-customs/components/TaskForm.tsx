// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import type CoreForm from '@rjsf/core';
import { Form } from '@rjsf/react-bootstrap';
import { customizeValidator } from '@rjsf/validator-ajv8';
import type {
  Experimental_DefaultFormStateBehavior,
  RegistryFieldsType,
  RegistryWidgetsType,
} from '@rjsf/utils';

import '@/rjsf-customs/components/TaskForm.scss';

import CustomNullField from '@/rjsf-customs/custom-fields/CustomNullField';
import { CustomObjectFieldTemplate } from '@/rjsf-customs/templates/ObjectFieldTemplate';
import CustomArrayFieldItemTemplate from '@/rjsf-customs/templates/ArrayFieldItemTemplate';
import CustomArrayFieldTemplate from '@/rjsf-customs/templates/ArrayFieldTemplate';
import CustomComboBox from '@/rjsf-customs/custom-widgets/CustomComboBox';
import CustomSchemaField from '@/rjsf-customs/custom-fields/CustomSchemaField';
import CustomArraySchemaField from '@/rjsf-customs/custom-fields/CustomArraySchemaField';
import CustomMultiFileField from '@/rjsf-customs/custom-fields/multiFileField/CustomMultiFileField';
import CustomSingleFileField from '@/rjsf-customs/custom-fields/multiFileField/CustomSingleFileField';
import {
  addNativeErrors,
  focusFirstError,
  validateOnInvalid,
} from '@/rjsf-customs/nativeValidation';
import { skipMinItemsPopulation } from '@/rjsf-customs/arrayDefaults';
import CustomSelect from '@/rjsf-customs/custom-widgets/CustomSelect';
import CustomCheckbox from '@/rjsf-customs/custom-widgets/CustomCheckbox';
import CustomTextWidget from '@/rjsf-customs/custom-widgets/CustomTextWidget';
import CustomDateWidget from '@/rjsf-customs/custom-widgets/CustomDateWidget';
import CurrencyNumberWidget from '@/rjsf-customs/custom-widgets/CurrencyNumberWidget';
import CustomFieldErrorTemplate from '@/rjsf-customs/templates/CustomFieldErrorTemplate';
import CustomDescriptionFieldTemplate from '@/rjsf-customs/templates/CustomDescriptionFieldTemplate';
import CustomFieldTemplate from '@/rjsf-customs/templates/CustomFieldTemplate';
import MultiSelectDynamic from '@/rjsf-customs/custom-widgets/MultiSelectDynamic';
import MultiSelectStatic from '@/rjsf-customs/custom-widgets/MultiSelectStatic';
import SelectDynamic from '@/rjsf-customs/custom-widgets/SelectDynamic';
import SelectStatic from '@/rjsf-customs/custom-widgets/SelectStatic';
import {
  collectHiddenPaths,
  dropErrorsOfHiddenFields,
  type FormPath,
} from '@/services/FeelService';
import { collectBlankRequiredPaths } from '@/services/emptyValues';
import { useTranslation } from '@/i18n';

// Patterns use the backend regex dialect. Leave their evaluation to submit;
// the remaining JSON Schema constraints still run in the browser.
const validator = customizeValidator({
  extenderFn: ajv => ajv.removeKeyword('pattern'),
});

const TRANSLATED_ERRORS = new Set([
  'required',
  'minLength',
  'maxLength',
  'minimum',
  'maximum',
  'minItems',
]);

// Restore rjsf v5 semantics: selects/radios are rendered as oneOf of {const, title},
// and v6's const-as-defaults would otherwise prefill them with their first option.
const defaultFormStateBehavior: Experimental_DefaultFormStateBehavior = {
  constAsDefaults: 'never',
  arrayMinItems: {
    computeSkipPopulate: (_validator, schema) => skipMinItemsPopulation(schema),
  },
};

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
  TextWidget: CustomTextWidget,
  DateWidget: CustomDateWidget,
  CurrencyNumberWidget,
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
  DescriptionFieldTemplate: CustomDescriptionFieldTemplate,
  FieldTemplate: CustomFieldTemplate,
};

// Enter in a single-line field would submit the form implicitly; a task is only submitted
// via its submit button. Textareas, buttons and widgets that handle Enter themselves
// (react-select picks an option) still get the key.
const preventSubmitOnEnter = (event: React.KeyboardEvent<HTMLFormElement>) => {
  if (event.key === 'Enter' && event.target instanceof HTMLInputElement) {
    event.preventDefault();
  }
};

const FormWithoutEnterSubmit = React.forwardRef<
  HTMLFormElement,
  React.FormHTMLAttributes<HTMLFormElement> & { as?: React.ElementType }
>(({ as: FormTag = 'form', ...props }, ref) => (
  <FormTag {...props} ref={ref} onKeyDown={preventSubmitOnEnter} />
));
FormWithoutEnterSubmit.displayName = 'FormWithoutEnterSubmit';

type BaseFormProps = React.ComponentProps<typeof Form>;

// Disabled and read-only fields: the backend marks both with ui:disabled.
const collectLockedPaths = (
  uiSchema: unknown,
  formData: unknown,
  path: FormPath = []
): FormPath[] =>
  Object.entries((uiSchema ?? {}) as Record<string, any>).flatMap(([key, ui]) => {
    if (key.startsWith('ui:') || !ui || typeof ui !== 'object') return [];
    if (ui['ui:disabled'] === true) return [[...path, key]];
    const rows = (formData as Record<string, any> | undefined)?.[key];
    if (!ui.items || !Array.isArray(rows)) return [];
    return rows.flatMap((row, index) => collectLockedPaths(ui.items, row, [...path, key, index]));
  });

export type TaskFormProps = Omit<BaseFormProps, 'validator'> & {
  validator?: BaseFormProps['validator'];
};

const TaskForm: React.FC<TaskFormProps> = ({
  validator: providedValidator,
  templates,
  fields,
  widgets,
  showErrorList,
  experimental_defaultFormStateBehavior: providedDefaultFormStateBehavior,
  transformErrors: providedTransformErrors,
  customValidate: providedCustomValidate,
  children,
  ...rest
}) => {
  const { t } = useTranslation();

  const formRef = React.useRef<CoreForm>(null);

  React.useEffect(() => {
    const instance = formRef.current;
    if (instance)
      return validateOnInvalid(instance.formElement.current, () => instance.validateForm());
  }, []);

  const focusError = React.useCallback(() => {
    focusFirstError(formRef.current?.formElement.current);
  }, []);

  React.useEffect(() => {
    if (rest.extraErrors) focusError();
  }, [rest.extraErrors, focusError]);

  // Fields whose errors must not block the submit. The backend treats a hidden field and
  // everything below it as absent. A locked field holds the server's value, which the
  // backend does not validate and the user cannot repair.
  const uncheckedPaths = (uiSchema: BaseFormProps['uiSchema'], formData: unknown): FormPath[] => [
    ...collectHiddenPaths(uiSchema ?? rest.uiSchema, rest.schema, formData),
    ...collectLockedPaths(uiSchema ?? rest.uiSchema, formData),
  ];

  // Visibility is read from the same data the hide-if rendering uses (formContext.formData).
  const transformErrors: NonNullable<BaseFormProps['transformErrors']> = (errors, uiSchema) => {
    const formData =
      (rest.formContext as { formData?: unknown } | undefined)?.formData ?? rest.formData;
    const unchecked = uncheckedPaths(uiSchema, formData);
    const visibleErrors = dropErrorsOfHiddenFields(errors, unchecked).map(error => {
      if (
        error.name === 'const' &&
        error.params?.allowedValue === true &&
        /\/properties\/[^/]+\/const$/.test(error.schemaPath ?? '')
      ) {
        return { ...error, message: t('formErrors.checkboxRequired') };
      }
      if (!error.name || !TRANSLATED_ERRORS.has(error.name)) return error;
      const limit = error.params?.limit;
      const key = error.name === 'minItems' && limit === 1 ? 'minItemsOne' : error.name;
      return { ...error, message: t(`formErrors.${key}`, { limit: limit ?? '' }) };
    });
    return providedTransformErrors
      ? providedTransformErrors(visibleErrors, uiSchema)
      : visibleErrors;
  };

  // 'required' means a value was entered: an emptied field is null (ui:emptyValue) and a
  // whitespace-only one a string, and both pass AJV's presence check - they are reported
  // here instead. Custom errors bypass transformErrors, so unchecked fields are skipped up front.
  const customValidate: NonNullable<BaseFormProps['customValidate']> = (
    formData,
    errors,
    uiSchema,
    schemaErrors
  ) => {
    const unchecked = uncheckedPaths(uiSchema, formData);
    for (const path of collectBlankRequiredPaths(rest.schema, formData, unchecked)) {
      const handler = path.reduce((current: any, segment) => current?.[segment], errors);
      handler?.addError?.(t('formErrors.required'));
    }
    const customErrors =
      providedCustomValidate?.(formData, errors, uiSchema, schemaErrors) ?? errors;
    addNativeErrors(formRef.current?.formElement.current, customErrors, schemaErrors, t);
    return customErrors;
  };

  return (
    <Form
      {...rest}
      ref={formRef}
      _internalFormWrapper={FormWithoutEnterSubmit}
      validator={providedValidator ?? validator}
      onError={rest.onError ?? focusError}
      transformErrors={transformErrors}
      customValidate={customValidate}
      templates={templates ?? customTemplates}
      fields={fields ?? customFields}
      widgets={widgets ?? customWidgets}
      experimental_defaultFormStateBehavior={
        providedDefaultFormStateBehavior ?? defaultFormStateBehavior
      }
      showErrorList={showErrorList ?? false}>
      {children ?? <></>}
    </Form>
  );
};

export { validator as taskFormValidator, customFields, customWidgets, customTemplates };
export default TaskForm;
