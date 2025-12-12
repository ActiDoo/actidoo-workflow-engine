import { WidgetProps } from '@rjsf/utils';
import React, { ReactElement, useCallback, useEffect, useRef, useState } from 'react';
import { MultiValue, SingleValue } from 'react-select';
import { useMutation } from 'react-query';
import { fetchPost } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { useParams } from 'react-router-dom';
import { FilterOptionOption } from 'react-select/dist/declarations/src/filters';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { PcValueLabelItem } from '@/models/models';
import { debounce } from 'lodash';

const CustomComboBox = (props: WidgetProps): ReactElement => {
  const [options, setOptions] = useState<PcValueLabelItem[] | undefined>(undefined);
  const [optionsLoaded, setOptionsLoaded] = useState<boolean>(false);
  const [selectedOption, setSelectedOption] = useState<
    PcValueLabelItem | PcValueLabelItem[] | undefined | null
  >(undefined);
  const [search, setSearch] = useState<string>('');
  const isMultiple = props.schema.type === 'array';
  const isDisabled = props.disabled ?? props.readonly;
  const lastValueChangeRef = useRef(Date.now());
  const { taskId } = useParams();

  const optionsQuery = useMutation({
    mutationFn: async () => {
      if (!props.uiSchema) {
        return {};
      }

      const res = await fetchPost(getApiUrl('user/search_property_options'), {
        task_id: taskId,
        property_path: props.uiSchema['ui:path'],
        search,
        include_value: props?.value,
        form_data: props?.formContext.formData,
      });

      return res.data;
    },
    onSuccess: (data: { options: PcValueLabelItem[] }) => {
      setOptions(data.options);
    },
    onError: () => {
      console.log('an error occurred');
    },
  });

  const debouncedMutate = useCallback(
    debounce(() => {
      optionsQuery.mutate();
    }, 300),
    [taskId, props.uiSchema ? props.uiSchema['ui:path'] : null]
  );

  useEffect(() => {
    debouncedMutate();
    return () => {
      debouncedMutate.cancel();
    };
  }, [search, props.value]);

  const handleChange = function (option: unknown): void {
    if (isMultiple) {
      const multiOptions = option as MultiValue<PcValueLabelItem>;
      const value = multiOptions.map(o => o.value);
      props.onChange(value);
    } else {
      const singleOption = option as SingleValue<PcValueLabelItem>;
      props.onChange(singleOption?.value);
    }
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

  useEffect(() => {
    const now = Date.now();
    lastValueChangeRef.current = now;

    if (!optionsLoaded) {
      debouncedMutate();
      setOptionsLoaded(true);
    } else {
      if (isMultiple) {
        setSelectedOption(options?.filter(o => props.value.indexOf(o.value) !== -1));
      } else {
        setSelectedOption(options?.find(o => o.value === props.value));
      }
    }
  }, [props.value, options, optionsLoaded]);

  if (props.uiSchema && 'ui:dependsOn' in props.uiSchema) {
    const dependsOn = props.uiSchema['ui:dependsOn'];
    // Create the dependency array directly using map and includes methods
    const effectDeps = dependsOn.map((dep: string) =>
      Object.prototype.hasOwnProperty.call(props.formContext?.formData, dep)
        ? props.formContext.formData[dep]
        : null
    );

    useEffect(() => {
      const now = Date.now();
      const timeSinceLastValueChange = now - (lastValueChangeRef.current || 0);
      //When the data is first filled into the form and there are already values for these fields, then all fields are filled "simultaneously".
      //Then all Change Events are processed "simultaneously".
      //Then it is determined that the Dependency field (e.g. Car Type) has changed and the dependent field (e.g. "Car Sub Type") is reset,
      //so the initial value is gone.
      //I have solved this with a time check that checks whether the two fields have changed in quick succession and then does not perform a reset.

      if (timeSinceLastValueChange > 1000) {
        setSelectedOption(null);
        setOptionsLoaded(false);
        setSearch('');
        setOptions([]);
        props.onChange('');
      }
    }, effectDeps);
  }

  return (
    <div>
      <WeComboBox
        value={selectedOption || ''}
        required={props.required}
        isLoading={optionsQuery.isLoading}
        options={options}
        isMulti={isMultiple}
        isDisabled={isDisabled}
        closeMenuOnSelect={!isMultiple}
        isClearable={
          /* it's clearable if there's a value which does not equal the default */
          ( !Array.isArray(selectedOption) && props.schema.default !== selectedOption?.value) ||
          ( Array.isArray(selectedOption) && props.schema.default !== selectedOption[0]?.value )}
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
export default CustomComboBox;
