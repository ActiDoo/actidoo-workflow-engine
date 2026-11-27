// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { getTemplate, localToUTC, utcToLocal, WidgetProps } from '@rjsf/utils';
import { ReactElement, useCallback } from 'react';

// rjsf's own date widgets turn an emptied date into undefined and ignore ui:emptyValue,
// so a cleared date never reached the server. These report the form's declared empty
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

// A date with time: shown in local time and kept in UTC, as rjsf's own widget does.
export const CustomDateTimeWidget = (props: WidgetProps): ReactElement => {
  const { onChange, value, options, registry } = props;
  const BaseInputTemplate = getTemplate('BaseInputTemplate', registry, options);
  const handleChange = useCallback(
    (local: unknown) => {
      onChange(localToUTC(local as string) ?? options.emptyValue);
    },
    [onChange, options.emptyValue]
  );
  return (
    <BaseInputTemplate
      type="datetime-local"
      {...props}
      value={utcToLocal(value)}
      onChange={handleChange}
    />
  );
};

export default CustomDateWidget;
