// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  FormContextType,
  getTemplate,
  getUiOptions,
  ObjectFieldTemplateProps,
  RJSFSchema,
  StrictRJSFSchema,
  titleId,
} from '@rjsf/utils';
import React, { ReactElement, useContext } from 'react';
import { ObjectDataContext } from '@/rjsf-customs/custom-widgets/dependsOn';
import { computeGridTemplate } from '@/rjsf-customs/templates/layoutColumns';

export function CustomObjectFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>(props: ObjectFieldTemplateProps<T, S, F>): ReactElement {
  const {
    registry,
    properties,
    title,
    description,
    uiSchema,
    required,
    schema,
    fieldPathId,
    formData,
  } = props;
  // console.log("** Object Field Template ********************************************************************************************")
  // console.log(props)
  const parentScope = useContext(ObjectDataContext);
  const options = getUiOptions<T, S, F>(uiSchema);
  const TitleFieldTemplate = getTemplate<'TitleFieldTemplate', T, S, F>(
    'TitleFieldTemplate',
    registry,
    options
  );
  const layout = uiSchema ? uiSchema['ui:layout'] : undefined;
  return (
    <ObjectDataContext.Provider value={{ formData, schema, parent: parentScope }}>
      <div>
        {title && (
          <TitleFieldTemplate
            id={titleId(fieldPathId)}
            title={title}
            required={required}
            schema={schema}
            uiSchema={uiSchema}
            registry={registry}
          />
        )}
        {description}
        {layout
          ? Object.keys(layout).map(rowId => {
              const itemNames: string[] = layout[rowId];
              const items = itemNames.map(name => {
                return properties.find(p => p.name === name);
              });
              const gridTemplateColumns = computeGridTemplate(
                itemNames.map(name => uiSchema?.[name]?.['ui:columns'])
              );
              return items.some(i => !i?.hidden) ? (
                <div className="row pc-row" style={{ gridTemplateColumns }} key={`pc-row-${rowId}`}>
                  {items.map((item, index) => {
                    return <div key={`pc-col-${item?.name}-${index}`}>{item?.content}</div>;
                  })}
                </div>
              ) : null;
            })
          : null}
      </div>
    </ObjectDataContext.Provider>
  );
}
