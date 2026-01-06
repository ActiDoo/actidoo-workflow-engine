// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { ReactElement, useEffect, useState } from 'react';
import { SingleValue } from 'react-select';
import { PcValueLabelItem } from '@/models/models';

const CustomSelect = (props: WidgetProps): ReactElement => {
  const [selectedOption, setSelectedOption] = useState<PcValueLabelItem | undefined>(props.value);
  const enumOptions = props.options.enumOptions;

  useEffect(() => {
    setSelectedOption(enumOptions?.find(o => o.value === props.value));
  }, [props.value]);

  const handleChange = (option: unknown): void => {
    const singleOption = option as SingleValue<PcValueLabelItem>;
    props.onChange(singleOption?.value);
  };

  return (
    <WeComboBox
      isClearable={props.schema.default !== selectedOption?.value}
      isSearchable={enumOptions ? enumOptions.length > 9 : false}
      value={selectedOption}
      isDisabled={props.disabled}
      required={props.required}
      options={enumOptions}
      onChange={d => {
        handleChange(d);
      }}
    />
  );
};
export default CustomSelect;
