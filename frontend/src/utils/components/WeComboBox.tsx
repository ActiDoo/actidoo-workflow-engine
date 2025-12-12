import Select from 'react-select';
import React from 'react';
import { StateManagerProps } from 'react-select/dist/declarations/src/useStateManager';

export const WeComboBox: React.FC<StateManagerProps> = props => {
  return (
    <Select
      {...props}
      isClearable={props.isClearable ?? true}
      styles={{
        control: (baseStyles, state) => ({
          ...baseStyles,
          fontSize: 'var(--sapFontSize)',
          boxShadow: 'none !important',
          minHeight: '34px',
          marginBottom: '0.25rem',
        }),
        indicatorSeparator: (baseStyles, state) => ({
          ...baseStyles,
          width: '0',
        }),
        clearIndicator: (baseStyles, state) => ({
          ...baseStyles,
          color: '#888888',
          padding: '6px 4px 6px 8px',
        }),
        dropdownIndicator: (baseStyles, state) => ({
          ...baseStyles,
          color: state.isDisabled ? '#cccccc' : '#000000',
          padding: '6px 8px 6px 4px',
        }),
        valueContainer: (baseStyles, state) => ({
          ...baseStyles,
          padding: '2px 8px 1px',
        }),
        option: (baseStyles, state) => ({
          ...baseStyles,
          fontSize: 'var(--sapFontSize)',
        }),
        /* zIndex = 20: thiy way items of a select box will overlap the label of a dynamic list */
        /* see ArrayFieldTemplate.tsx and see the usage of the z-10 class */
        menu: (baseStyles, state) => ({
          ...baseStyles,
          zIndex: 20
        })
      }}
      classNames={{
        control: state =>
          state.isFocused
            ? '!border-brand-primary '
            : state.isDisabled
            ? '!border-neutral-200 !bg-neutral-50 '
            : '!border-neutral-200 ',
        singleValue: state => (state.isDisabled ? '!text-neutral-700' : ''),
        option: state =>
          state.isSelected
            ? '!bg-brand-primary'
            : state.isFocused
            ? '!bg-neutral-50 !cursor-pointer'
            : 'hover:bg-neutral-50 cursor-pointer',        
      }}
    />
  );
};
