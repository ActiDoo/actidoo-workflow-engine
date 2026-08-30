// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { getTemplate, WidgetProps } from '@rjsf/utils';
import { ReactElement, useState } from 'react';

const CustomTextWidget = (props: WidgetProps): ReactElement => {
  const [cleared, setCleared] = useState(false);
  const BaseInputTemplate = getTemplate('BaseInputTemplate', props.registry, props.options);

  // An optional number field admits null: its type is ['number', 'null'].
  const type = Array.isArray(props.schema.type)
    ? props.schema.type.find(t => t !== 'null')
    : props.schema.type;
  if (type !== 'number' && type !== 'integer') {
    return <BaseInputTemplate {...props} />;
  }

  return (
    <BaseInputTemplate
      {...props}
      schema={{ ...props.schema, type }}
      value={cleared ? '' : props.value}
      onChange={(value, ...rest) => {
        setCleared(value === '' || value === undefined || value === null);
        props.onChange(value, ...rest);
      }}
      onFocus={(id, value) => {
        (document.getElementById(id) as HTMLInputElement | null)?.select();
        props.onFocus(id, value);
      }}
      onBlur={(id, value) => {
        setCleared(false);
        props.onBlur(id, value);
      }}
    />
  );
};

export default CustomTextWidget;
