// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { getTemplate, WidgetProps } from '@rjsf/utils';
import { ReactElement, useCallback } from 'react';

// rjsf's own date widget turns an emptied date into undefined and ignores ui:emptyValue,
// so a cleared date never reached the server. This one reports the form's declared empty
// value instead: null in forms handed out since empty fields are null, nothing in older
// running tasks whose schema does not admit null.
const CustomDateWidget = (props: WidgetProps): ReactElement => {
  const { onChange, options, registry } = props;
  const BaseInputTemplate = getTemplate('BaseInputTemplate', registry, options);
  const handleChange = useCallback(
    (value: unknown) => {
      onChange(value || options.emptyValue);
    },
    [onChange, options.emptyValue]
  );
  return <BaseInputTemplate type="date" {...props} onChange={handleChange} />;
};

export default CustomDateWidget;
