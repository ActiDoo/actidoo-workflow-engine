import { DateRangePicker, type DateRangePickerDomRef } from '@ui5/webcomponents-react';
import type { Ui5CustomEvent } from '@ui5/webcomponents-react';

interface Props {
  startSetter: React.Dispatch<React.SetStateAction<Date>>;
  endSetter: React.Dispatch<React.SetStateAction<Date>>;
}

export const DateSelection: React.FC<Props> = ({ startSetter, endSetter }) => {
    const today = new Date().toLocaleDateString();
    const lastYear = new Date(new Date().setFullYear(new Date().getFullYear() - 1))
    .toLocaleDateString()
    const placeholder = lastYear + ' - ' + today;

    const handleChange = (e: Ui5CustomEvent<DateRangePickerDomRef, { valid: boolean }>) => {
        if (e.detail.valid) {
        const el = e.target; // DateRangePickerDomRef
        startSetter(el.startDateValue ?? lastYear);
        endSetter(el.endDateValue ?? today);
        }
    };

    return (
        <div style={{paddingLeft: "50px"}}>
        <DateRangePicker
        minDate="2024-08-01"
        maxDate={today}
        formatPattern="dd.MM.yyyy"
        placeholder={placeholder}
        onChange={handleChange}
        />
        </div>
    );
};
