// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import { ChangeEvent, ReactElement } from 'react';

const CustomCheckbox = (props: WidgetProps): ReactElement => {
  // Controlled directly by props.value (undefined initially -> unchecked). Mirroring it
  // into local state via a useEffect on [props] caused an infinite render loop under
  // rjsf 6, where the widget receives a fresh props object on every form render.
  const isChecked = !!props.value;

  function onCheckbox(_evt: ChangeEvent<HTMLInputElement>) {
    props.onChange(!isChecked); // propagate the new value, so WidgetProps can take care of it. Afterwards a re-render will happen.
  }

  return (
    <div className="mb-0">
      <div className="flex">
        <div>
          {/* we need a div around the input, otherwise the width of the input (the checkbox itself) will be too thin for long labels */}
          <input
            className="mr form-check-input"
            type="checkbox"
            checked={isChecked}
            onChange={evt => {
              onCheckbox(evt);
            }}
            required={props.required}
            disabled={props.disabled}
          />
        </div>
        <label className={'ml-2 text-sm' + (props.disabled ? 'opacity-75' : '')}>
          {props.required ? props.label + '*' : props.label}
        </label>
      </div>

      {/* That's the hint: */}
      <p className={'text-gray-500 text-xs ' + (props.disabled ? 'opacity-80' : '')}>
        {props.options.description}
      </p>
    </div>
  );
};
export default CustomCheckbox;
