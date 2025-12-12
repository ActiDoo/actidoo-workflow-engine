import { WidgetProps } from '@rjsf/utils';
import { WeComboBox } from '@/utils/components/WeComboBox';
import { ReactElement, useEffect, useState } from 'react';
import { SingleValue } from 'react-select';
import { PcValueLabelItem } from '@/models/models';

const SelectStatic = (props: WidgetProps): ReactElement => {
  const [selectedOption, setSelectedOption] = useState<PcValueLabelItem | null>(props.value);
  
  const enumOptions = props.options.enumOptions?.filter(o => o.value !== null); //filter the "null" value

  //console.log(`SelectStatic: ${JSON.stringify(enumOptions)} -> ${props.value}`)

  const getSelectionOption = function () {
    let opt = enumOptions?.find(o => o.value === props.value)
    if (!opt) {
      return null //prevent returning undefined, otherwise cleared data from a selection is not included in the JSON payload
    } else
      return opt
  }

  useEffect(() => {
    setSelectedOption(getSelectionOption());
  }, [props.value]);

  const handleChange = (option: unknown): void => {
    let singleOption = option as SingleValue<PcValueLabelItem>;
    //When WeComboBox is cleared (X pressed), then "option" is null and so "singleOption.value" is undefined 
    //When null value is explicitly chosen (JSONschema must include this as option) then singleOption.value = null
    if (!singleOption || !singleOption.value) {
      props.onChange(null)
      return
    }
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
export default SelectStatic;
