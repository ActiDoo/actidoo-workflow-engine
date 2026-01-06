// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { DatePicker, DatePickerDomRef, Icon } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import '@ui5/webcomponents-icons/dist/decline';
import { useAutoFocus } from '@/ui5-components/services/HelperService';
import { StringDict } from '@/ui5-components/models/models';

export interface PcDateFilterProps {
  filter: StringDict;
  onFilter: (id: string, val: string | undefined) => {};
  column: { val: string; id: string };
}

function toIsoDateOnly(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export const PcDateFilter: React.FC<PcDateFilterProps> = props => {
  const ref: React.Ref<DatePickerDomRef> = useAutoFocus();
  const filterId = props.column.id + '_eq';
  const value = props.filter[filterId] ?? '';

  return (
    <>
      <DatePicker
        ref={ref}
        value={value}
        onChange={e => props.onFilter(filterId, e.target.dateValue ? toIsoDateOnly(e.target.dateValue) : '')}
      />
      <Icon
        name="decline"
        className={`ml-2 ${value ? 'cursor-pointer' : 'text-gray-300'}`}
        onClick={() => (value ? props.onFilter(filterId, '') : null)}
      />
    </>
  );
};
