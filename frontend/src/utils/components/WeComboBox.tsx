// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import Select, { components, MenuListProps } from 'react-select';
import React, { MutableRefObject, UIEvent, useEffect, useRef } from 'react';
import { StateManagerProps } from 'react-select/dist/declarations/src/useStateManager';

const SCROLL_TO_BOTTOM_THRESHOLD_PX = 24;

const isScrolledToBottom = (el: HTMLElement): boolean =>
  el.scrollTop + el.clientHeight >= el.scrollHeight - SCROLL_TO_BOTTOM_THRESHOLD_PX;

const MenuList = (props: MenuListProps<any, boolean>) => {
  const { onMenuScrollToBottom, isLoading } = props.selectProps;
  const listRef = useRef<HTMLDivElement | null>(null);

  const setRefs = (el: HTMLDivElement | null) => {
    listRef.current = el;
    if (typeof props.innerRef === 'function') {
      props.innerRef(el);
    } else if (props.innerRef) {
      (props.innerRef as MutableRefObject<HTMLDivElement | null>).current = el;
    }
  };

  const handleScroll = (event: UIEvent<HTMLDivElement>) => {
    if (onMenuScrollToBottom && isScrolledToBottom(event.currentTarget)) {
      onMenuScrollToBottom(event.nativeEvent as unknown as WheelEvent);
    }
  };

  useEffect(() => {
    const el = listRef.current;
    if (!el || !onMenuScrollToBottom || isLoading) return;
    if (el.scrollHeight <= el.clientHeight) {
      onMenuScrollToBottom(new WheelEvent('wheel'));
    }
  }, [props.options.length, isLoading, onMenuScrollToBottom]);

  return (
    <components.MenuList
      {...props}
      innerRef={setRefs}
      innerProps={{ ...props.innerProps, onScroll: handleScroll }}
    />
  );
};

export const WeComboBox: React.FC<StateManagerProps> = props => {
  return (
    <Select
      {...props}
      components={{ MenuList, ...props.components }}
      isClearable={props.isClearable ?? true}
      // Opening a select must not scroll the page — react-select's default made the
      // view jump inside our scrolling layout. When there is no space below, the menu
      // opens upwards instead.
      menuPlacement={props.menuPlacement ?? 'auto'}
      menuShouldScrollIntoView={props.menuShouldScrollIntoView ?? false}
      styles={{
        control: (baseStyles, _state) => ({
          ...baseStyles,
          fontSize: 'var(--sapFontSize)',
          boxShadow: 'none !important',
          minHeight: '34px',
          marginBottom: '0.25rem',
        }),
        indicatorSeparator: (baseStyles, _state) => ({
          ...baseStyles,
          width: '0',
        }),
        clearIndicator: (baseStyles, _state) => ({
          ...baseStyles,
          color: '#888888',
          padding: '6px 4px 6px 8px',
        }),
        dropdownIndicator: (baseStyles, state) => ({
          ...baseStyles,
          color: state.isDisabled ? '#cccccc' : '#000000',
          padding: '6px 8px 6px 4px',
        }),
        valueContainer: (baseStyles, _state) => ({
          ...baseStyles,
          padding: '2px 8px 1px',
        }),
        option: (baseStyles, _state) => ({
          ...baseStyles,
          fontSize: 'var(--sapFontSize)',
        }),
        /* zIndex = 20: thiy way items of a select box will overlap the label of a dynamic list */
        /* see ArrayFieldTemplate.tsx and see the usage of the z-10 class */
        menu: (baseStyles, _state) => ({
          ...baseStyles,
          zIndex: 20,
        }),
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
