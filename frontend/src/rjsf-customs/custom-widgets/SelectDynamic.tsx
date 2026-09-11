// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import React, { ReactElement, useEffect, useRef, useState } from 'react';
import { SingleValue } from 'react-select';
import { useParams } from 'react-router-dom';
import { FilterOptionOption } from 'react-select/dist/declarations/src/filters';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { PcValueLabelItem } from '@/models/models';
import { usePropertyOptions } from '@/rjsf-customs/hooks/usePropertyOptions';

const SelectDynamic = (props: WidgetProps): ReactElement => {
  const [optionsLoaded, setOptionsLoaded] = useState<boolean>(false);
  const [selectedOption, setSelectedOption] = useState<PcValueLabelItem | null>(null);
  const [search, setSearch] = useState<string>('');
  const isDisabled = props.disabled ?? props.readonly;
  const lastValueChangeRef = useRef(Date.now());
  const { taskId } = useParams();
  const effectiveTaskId = taskId ?? (props.registry as any)?.formContext?.taskId;

  const { options, isLoading, loadMore, reload, cancelReload, clear } = usePropertyOptions({
    taskId: effectiveTaskId,
    propertyPath: props.uiSchema ? props.uiSchema['ui:path'] : undefined,
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
    const now = Date.now();
    lastValueChangeRef.current = now;

    if (!optionsLoaded) {
      reload();
      setOptionsLoaded(true);
    } else {
      setSelectedOption(getSelectionOption());
    }
  }, [props.value, options, optionsLoaded]);

  if (props.uiSchema && 'ui:dependsOn' in props.uiSchema) {
    const dependsOn = props.uiSchema['ui:dependsOn'];
    const formContextFormData = (props.registry as any)?.formContext?.formData;
    const effectDeps = dependsOn.map((dep: string) =>
      formContextFormData && Object.prototype.hasOwnProperty.call(formContextFormData, dep)
        ? formContextFormData[dep]
        : null
    );

    useEffect(() => {
      const now = Date.now();
      const timeSinceLastValueChange = now - (lastValueChangeRef.current || 0);
      // When the data is first filled into the form and there are already values for these fields, then all fields are filled "simultaneously".
      // Then all Change Events are processed "simultaneously".
      // Then it is determined that the Dependency field (e.g. Car Type) has changed and the dependent field (e.g. "Car Sub Type") is reset,
      // so the initial value is gone.
      // I have solved this with a time check that checks whether the two fields have changed in quick succession and then does not perform a reset.

      if (timeSinceLastValueChange > 1000) {
        setSelectedOption(null);
        setOptionsLoaded(false);
        setSearch('');
        clear();
        props.onChange('');
      }
    }, effectDeps);
  }

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
