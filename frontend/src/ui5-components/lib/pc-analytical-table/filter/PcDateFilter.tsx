import React from 'react';
import { DatePicker, DatePickerDomRef, Icon } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import { useAutoFocus } from '@/ui5-components/services/HelperService';
import moment from 'moment';
import { StringDict } from '@/ui5-components/models/models';

export interface PcDateFilterProps {
  filter: StringDict;
  onFilter: (id: string, val: string | undefined) => {};
  column: { val: string; id: string };
}

export const PcDateFilter: React.FC<PcDateFilterProps> = props => {
  const ref: React.Ref<DatePickerDomRef> = useAutoFocus();
  const dateString = (val: string): string => {
    return moment(val, 'DD.MM.YYYY').toISOString(true).split('T')[0];
  };
  const formattedVal = props.filter[props.column.id + '_eq']
    ? moment(props.filter[props.column.id + '_eq']).format('DD.MM.YYYY')
    : '';

  return (
    <>
      <DatePicker
        ref={ref}
        value={formattedVal}
        onChange={e => {
          // debugger;
          props.onFilter(props.column?.id + '_eq', dateString(e.detail.value));
        }}
      />
      <Icon
        name="decline"
        className={`ml-2 ${formattedVal ? 'cursor-pointer' : 'text-gray-300'}`}
        onClick={() => (formattedVal ? props.onFilter(props.column?.id + '_eq', '') : null)}
      />
    </>
  );
};
