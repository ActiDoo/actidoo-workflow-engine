// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import React, { ReactElement, useEffect, useRef, useState } from 'react';
import { SingleValue } from 'react-select';
import { useParams } from 'react-router-dom';
import { FilterOptionOption } from 'react-select/dist/declarations/src/filters';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { PcValueLabelItem } from '@/models/models';
import { isEqual } from 'lodash';
import { getPropertyPath, useDependencyValues } from '@/rjsf-customs/custom-widgets/dependsOn';
import { usePropertyOptions } from '@/rjsf-customs/hooks/usePropertyOptions';

const SelectDynamic = (props: WidgetProps): ReactElement => {
  const [optionsLoaded, setOptionsLoaded] = useState<boolean>(false);
  const [selectedOption, setSelectedOption] = useState<PcValueLabelItem | null>(null);
  const [search, setSearch] = useState<string>('');
  const isDisabled = Boolean(props.disabled || props.readonly);
  const { taskId } = useParams();
  const effectiveTaskId = taskId ?? (props.registry as any)?.formContext?.taskId;

  const { options, isLoading, loadMore, reload, cancelReload, clear } = usePropertyOptions({
    taskId: effectiveTaskId,
    propertyPath: props.uiSchema ? getPropertyPath(props.id, props.uiSchema['ui:path']) : undefined,
    search,
    includeValue: props?.value,
    formData: (props.registry as any)?.formContext?.formData,
  });

  useEffect(() => {
    reload();
    return () => {
      cancelReload();
    };
  }, [search, props.value]);

  const handleChange = function (option: unknown): void {
    const singleOption = option as SingleValue<PcValueLabelItem>;
    if (!singleOption?.value) {
      props.onChange(null);
      return;
    }
    props.onChange(singleOption?.value);
  };

  const handleFilter = function (option: FilterOptionOption<any>, inputValue: string): boolean {
    return inputValue
      .toLocaleLowerCase()
      .split(' ')
      .every(
        word =>
          option.label.toLowerCase().includes(word) || option.value.toLowerCase().includes(word)
      );
  };

  const getSelectionOption = function () {
    const opts = options?.find(o => o.value === props.value);
    if (opts === undefined)
      return null; // prevent returning undefined, otherwise cleared data from a selection is not included in the JSON payload
    else return opts;
  };

  useEffect(() => {
    if (!optionsLoaded) {
      reload();
      setOptionsLoaded(true);
    } else {
      setSelectedOption(getSelectionOption());
    }
  }, [props.value, options, optionsLoaded]);

  const effectDeps = useDependencyValues(
    props.uiSchema?.['ui:dependsOn'],
    (props.registry as any)?.formContext
  );
  const prevDepsRef = useRef(effectDeps);
  const prevValueRef = useRef(props.value);

  useEffect(() => {
    const changed = !isEqual(effectDeps, prevDepsRef.current);
    prevDepsRef.current = effectDeps;
    if (!changed || isDisabled) return;
    setSelectedOption(null);
    setOptionsLoaded(false);
    setSearch('');
    clear();
    if (props.value && props.value === prevValueRef.current) props.onChange(null);
  }, effectDeps);

  useEffect(() => {
    prevValueRef.current = props.value;
  });

  return (
    <div>
      <WeComboBox
        inputId={props.id}
        value={selectedOption ?? ''}
        required={props.required}
        isLoading={isLoading}
        options={options}
        isDisabled={isDisabled}
        isClearable={
          props.schema.default !== selectedOption?.value
        } /* it's clearable if there's a value which does not equal the default */
        onInputChange={value => {
          setSearch(value);
        }}
        onChange={e => {
          handleChange(e);
        }}
        onMenuScrollToBottom={loadMore}
        filterOption={(option, inputValue) => handleFilter(option, inputValue)}
      />
    </div>
  );
};
export default SelectDynamic;
