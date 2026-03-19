// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import React, { ReactElement, useEffect, useState } from 'react';
import { MultiValue } from 'react-select';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { PcValueLabelItem } from '@/models/models';

const MultiSelectStatic = (props: WidgetProps): ReactElement => {
  const [selectedOptions, setSelectedOptions] = useState<PcValueLabelItem[]>([]);
  const isDisabled = props.disabled ?? props.readonly;

  // Explanation of the jsonschema:
  // props.schema.items.oneOf =
  // [{"const":"value5","title":"Value 5"},{"const":"value6","title":"Value 6"},{"const":"value7","title":"Value 7"}]
  const schemaOptions =
    (
      props.schema?.items as {
        oneOf?: Array<{
          title: any;
          const: any;
        }>;
      }
    )?.oneOf ?? [];
  // WeComboBox expects value/label:
  const options = schemaOptions.map(option => ({
    value: option.const, // use "const" as "value"
    label: option.title, // use "title" as "label"
  }));

  // console.log(`MultiSelectStatic: ${options} -> ${props.value}`)

  const getRemainingOptions = function () {
    // use the possible selections from the jsonschema and filter already selected values:
    const opts = options?.filter(o => props.value.indexOf(o.value) === -1) || [];
    return opts;
  };

  const getSelectedOptions = function () {
    const opts = options?.filter(o => props.value.indexOf(o.value) !== -1) || [];
    return opts;
  };

  useEffect(() => {
    setSelectedOptions(getSelectedOptions());
  }, [props.value]);

  const handleChange = function (option: unknown): void {
    const multiOptions = option as MultiValue<PcValueLabelItem>;
    const value = multiOptions.map(o => o.value);
    console.log(value);
    props.onChange(value);
  };

  return (
    <div>
      <WeComboBox
        value={selectedOptions}
        required={props.required}
        options={getRemainingOptions()}
        isMulti={true}
        isDisabled={isDisabled}
        closeMenuOnSelect={false}
        isClearable={
          /* it's clearable if there's a value which does not equal the default */
          props.schema.default !== selectedOptions[0]?.value
        }
        onChange={e => {
          handleChange(e);
        }}
      />
    </div>
  );
};
export default MultiSelectStatic;
