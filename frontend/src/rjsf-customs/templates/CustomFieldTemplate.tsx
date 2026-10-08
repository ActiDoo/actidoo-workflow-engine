// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  FieldTemplateProps,
  FormContextType,
  getTemplate,
  getUiOptions,
  RJSFSchema,
  StrictRJSFSchema,
} from '@rjsf/utils';
import Form from 'react-bootstrap/Form';

// The FieldTemplate of @rjsf/react-bootstrap, except that the widget, description, errors
// and help sit in one div below the label. In a form row (ui:layout) the label and that div
// take the two grid rows of the field, so the inputs of a row line up (TaskForm.scss).
export default function CustomFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>({
  id,
  children,
  displayLabel,
  rawErrors = [],
  errors,
  help,
  description,
  rawDescription,
  classNames,
  style,
  disabled,
  label,
  hidden,
  onKeyRename,
  onKeyRenameBlur,
  onRemoveProperty,
  readonly,
  required,
  schema,
  uiSchema,
  registry,
}: FieldTemplateProps<T, S, F>) {
  const uiOptions = getUiOptions(uiSchema);
  const WrapIfAdditionalTemplate = getTemplate<'WrapIfAdditionalTemplate', T, S, F>(
    'WrapIfAdditionalTemplate',
    registry,
    uiOptions
  );
  if (hidden) {
    return <div className="hidden">{children}</div>;
  }
  const isCheckbox = uiOptions.widget === 'checkbox';

  return (
    <WrapIfAdditionalTemplate
      classNames={classNames}
      style={style}
      disabled={disabled}
      id={id}
      label={label}
      displayLabel={displayLabel}
      rawDescription={rawDescription}
      onKeyRename={onKeyRename}
      onKeyRenameBlur={onKeyRenameBlur}
      onRemoveProperty={onRemoveProperty}
      readonly={readonly}
      required={required}
      schema={schema}
      uiSchema={uiSchema}
      registry={registry}>
      <Form.Group>
        {displayLabel && !isCheckbox && (
          <Form.Label htmlFor={id} className={rawErrors.length > 0 ? 'text-danger' : ''}>
            {label}
            {required ? '*' : null}
          </Form.Label>
        )}
        <div className="pc-field-content">
          {children}
          {displayLabel && rawDescription && !isCheckbox && (
            <Form.Text className={rawErrors.length > 0 ? 'text-danger' : 'text-muted'}>
              {description}
            </Form.Text>
          )}
          {errors}
          {help}
        </div>
      </Form.Group>
    </WrapIfAdditionalTemplate>
  );
}
