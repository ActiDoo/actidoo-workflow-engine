import React from 'react';
import { Option, Select, Text, ValueState } from '@ui5/webcomponents-react';
import { PcDetailsSectionItem } from '../models/PcEditableDetailsSectionModels';

interface PcSelectProps {
  item: PcDetailsSectionItem;
  onChange: (values: string | undefined) => void;
  isEditable: boolean;
  valueState: ValueState;
  selected: string;
  valueStateMessage?: string;
}
export function PcSelect(props: PcSelectProps): React.ReactElement {
  return (
    <Select
      className="flex-1"
      required={props.item.required}
      disabled={props.item.readonly ?? !props.isEditable}
      valueState={props.valueState}
      valueStateMessage={<Text>{props.valueStateMessage}</Text>}
      onChange={e => {
        props.item.key && props.onChange(e.detail.selectedOption.dataset.value);
      }}>
      <Option data-value={undefined}>-</Option>
      {props.item.options?.map(o => (
        <Option key={o.value} data-value={o.value} selected={props.selected === o.value}>
          {o.label}
        </Option>
      ))}
    </Select>
  );
}
