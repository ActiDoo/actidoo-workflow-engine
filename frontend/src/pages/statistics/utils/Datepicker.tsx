// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { DateRangePicker, type DateRangePickerDomRef } from '@ui5/webcomponents-react';
import type { Ui5CustomEvent } from '@ui5/webcomponents-react';
import type { Dispatch, SetStateAction } from 'react';

interface Props {
  startSetter: Dispatch<SetStateAction<Date>>;
  endSetter: Dispatch<SetStateAction<Date>>;
}

export const DateSelection: React.FC<Props> = ({ startSetter, endSetter }) => {
  const today = new Date();
  const lastYear = new Date(today);
  lastYear.setFullYear(today.getFullYear() - 1);

  const placeholder = `${lastYear.toLocaleDateString()} - ${today.toLocaleDateString()}`;
  const todayIso = today.toISOString().slice(0, 10);

  const handleChange = (e: Ui5CustomEvent<DateRangePickerDomRef, { valid: boolean }>) => {
    if (!e.detail.valid) return;
    const el = e.target; // DateRangePickerDomRef
    startSetter(el.startDateValue ?? lastYear);
    endSetter(el.endDateValue ?? today);
  };

  return (
    <div style={{ paddingLeft: '50px' }}>
      <DateRangePicker
        minDate="2024-08-01"
        maxDate={todayIso}
        formatPattern="dd.MM.yyyy"
        placeholder={placeholder}
        onChange={handleChange}
      />
    </div>
  );
};
