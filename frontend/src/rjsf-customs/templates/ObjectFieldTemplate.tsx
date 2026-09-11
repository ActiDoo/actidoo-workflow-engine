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
import React, { ReactElement } from 'react';

export function CustomObjectFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>(props: ObjectFieldTemplateProps<T, S, F>): ReactElement {
  const { registry, properties, title, description, uiSchema, required, schema, fieldPathId } =
    props;
  // console.log("** Object Field Template ********************************************************************************************")
  // console.log(props)
  const options = getUiOptions<T, S, F>(uiSchema);
  const TitleFieldTemplate = getTemplate<'TitleFieldTemplate', T, S, F>(
    'TitleFieldTemplate',
    registry,
    options
  );
  const layout = uiSchema ? uiSchema['ui:layout'] : undefined;
  const generateClassCol = (length: number): string => {
    switch (length) {
      case 1:
        return 'col-md-12';
      case 2:
        return 'col-lg-6';
      case 3:
        return 'col-lg-4';
      case 4:
        return 'col-lg-3';
      default:
        return 'col-lg';
    }
  };

  return (
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
            const classColl = generateClassCol(items.length);
            return items.some(i => !i?.hidden) ? (
              <div className="row align-items-end" key={`pc-row-${rowId}`}>
                {items.map((item, index) => {
                  return (
                    <div className={classColl} key={`pc-col-${item?.name}-${index}`}>
                      {item?.content}
                    </div>
                  );
                })}
              </div>
            ) : null;
          })
        : null}
    </div>
  );
}
