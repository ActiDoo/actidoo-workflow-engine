// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import { Icon } from '@ui5/webcomponents-react';

export interface PcAnalyticalTableHeaderProps {
  name: string;
  filtered: boolean;
  sortDirection: string | undefined;
}

export const PcAnalyticalTableHeader: React.FC<PcAnalyticalTableHeaderProps> = props => {
  return (
    <>
      {props.filtered ? (
        <span className=" mr-1">
          <Icon className="w-3 h-3" name="filter" />
        </span>
      ) : null}
      {props.sortDirection === 'asc' ? (
        <span className=" mr-1">
          <Icon className="w-3 h-3" name="sort-ascending" />
        </span>
      ) : null}
      {props.sortDirection === 'desc' ? (
        <span className=" mr-1">
          <Icon className="w-3 h-3" name="sort-descending" />
        </span>
      ) : null}
      {props.name}
    </>
  );
};
