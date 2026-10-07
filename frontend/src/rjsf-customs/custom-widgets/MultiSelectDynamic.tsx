// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WidgetProps } from '@rjsf/utils';
import React, { ReactElement, useCallback, useEffect, useRef, useState } from 'react';
import { MultiValue } from 'react-select';
import { useMutation } from 'react-query';
import { fetchPost } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { useParams } from 'react-router-dom';
import { FilterOptionOption } from 'react-select/dist/declarations/src/filters';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { PcValueLabelItem } from '@/models/models';
import { debounce, isEqual } from 'lodash';
import { useDispatch } from 'react-redux';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { stripAttachmentPayload } from '@/rjsf-customs/custom-fields/multiFileField/attachments';
import { getPropertyPath, useDependencyValues } from '@/rjsf-customs/custom-widgets/dependsOn';

const MultiSelectDynamic = (props: WidgetProps): ReactElement => {
  const [options, setOptions] = useState<PcValueLabelItem[] | undefined>(undefined);
  const [optionsLoaded, setOptionsLoaded] = useState<boolean>(false);
  const [selectedOptions, setSelectedOptions] = useState<PcValueLabelItem[]>([]);
  const [search, setSearch] = useState<string>('');
  const isDisabled = props.disabled ?? props.readonly;
  const dispatch = useDispatch();
  const { taskId } = useParams();
  const effectiveTaskId = taskId ?? (props.registry as any)?.formContext?.taskId;

  // console.log(`MultiSelectDynamic: ${JSON.stringify(options)} -> ${props.value}`)

  const optionsQuery = useMutation({
    mutationFn: async () => {
      if (!props.uiSchema) {
        return {};
      }

      if (!effectiveTaskId) {
        return { options: [] };
      }

      const res = await fetchPost(getApiUrl('user/search_property_options'), {
        task_id: effectiveTaskId,
        property_path: getPropertyPath(props.id, props.uiSchema['ui:path']),
        search,
        include_value: props?.value,
        form_data: stripAttachmentPayload((props.registry as any)?.formContext?.formData),
      });

      // console.log(`opts = ${JSON.stringify(res.data)}`)
      // e.g. {"options":[{"value":"three","label":"Option Drei"},{"value":"one","label":"Option Eins"},{"value":"two","label":"Option Zwei"}]}

      return res.data;
    },
    onSuccess: (data: { options: PcValueLabelItem[] }) => {
      setOptions(data.options);
    },
    onError: () => {
      // Keep the field usable after a failed search: clear the loading/stale state so the
      // menu shows the standard "no options" and a corrected input re-triggers the search.
      setOptions([]);
      dispatch(addToast(<WeToastContent text={`Could not load options. Please try again.`} />));
    },
  });

  const debouncedMutate = useCallback(
    // debouncedMutate will stay the same during re-render, as long as the deps don't change
    debounce(() => {
      optionsQuery.mutate();
    }, 300),
    [effectiveTaskId, props.uiSchema ? props.uiSchema['ui:path'] : null]
  );

  useEffect(() => {
    debouncedMutate();
    return () => {
      debouncedMutate.cancel(); // cleanup function that runs every re-render and on unmount
    };
  }, [search, props.value]); // TODO hier werden sich IN JEDEM FALL dynamisch die Werte geholt

  const handleChange = function (option: unknown): void {
    const multiOptions = option as MultiValue<PcValueLabelItem>;
    const value = multiOptions.map(o => o.value);
    props.onChange(value);
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

  const getSelectionOptions = function () {
    const opts = options?.filter(o => props.value.indexOf(o.value) !== -1);
    if (opts === undefined)
      return []; // prevent returning undefined, otherwise cleared data from a selection is not included in the JSON payload
    else return opts;
  };

  useEffect(() => {
    if (!optionsLoaded) {
      debouncedMutate();
      setOptionsLoaded(true);
    } else {
      setSelectedOptions(getSelectionOptions());
    }
    // no return value with clean-up code like "debouncedMutate.cancel()"", because that's done in the other useEffect() definition
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
    if (!changed) return;
    setSelectedOptions([]);
    setOptionsLoaded(false);
    setSearch('');
    setOptions([]);
    if (props.value?.length && isEqual(props.value, prevValueRef.current)) props.onChange([]);
  }, effectDeps);

  useEffect(() => {
    prevValueRef.current = props.value;
  });

  return (
    <div>
      <WeComboBox
        value={selectedOptions || ''}
        required={props.required}
        isLoading={optionsQuery.isLoading}
        options={options}
        isMulti={true}
        isDisabled={isDisabled}
        closeMenuOnSelect={false}
        isClearable={
          /* it's clearable if there's a value which does not equal the default */
          props.schema.default !== selectedOptions[0]?.value
        }
        onInputChange={value => {
          setSearch(value);
        }}
        onChange={e => {
          handleChange(e);
        }}
        filterOption={(option, inputValue) => handleFilter(option, inputValue)}
      />
    </div>
  );
};
export default MultiSelectDynamic;
