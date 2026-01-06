// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { Icon, Input, InputDomRef, InputType } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import { useAutoFocus } from '@/ui5-components/services/HelperService';

export interface PcInputFilterProps {
  val: string;
  onFilter: (id: string, val: string | undefined) => {};
  column: { val: string; id: string };
  type?: InputType;
}

export const PcInputFilter: React.FC<PcInputFilterProps> = props => {
  const ref: React.Ref<InputDomRef> = useAutoFocus();
  const id = `${props.column?.id}${props.type === InputType.Number ? '_eq' : ''}`;
  return (
    <>
      <Input
        type={props.type}
        ref={ref}
        value={props.val}
        onInput={e => {
          props.onFilter(id, e.target.value);
        }}
      />
      <Icon
        name="decline"
        className={`ml-2 ${props.val ? 'cursor-pointer' : 'text-gray-300'}`}
        onClick={() => (props.val ? props.onFilter(id, '') : null)}
      />
    </>
  );
};
