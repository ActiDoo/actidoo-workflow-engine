// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import {
  AnalyticalTableColumnDefinition,
  Option,
  Select,
  TextAlign,
} from '@ui5/webcomponents-react';
import { PcArrowLink, PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

const serviceUserFilter = (
  tableData: PcTableData,
  columnId: string,
  t: Translate
): React.ReactElement => {
  const currentVal = tableData.filter[columnId] ?? '';
  return (
    <Select
      className="w-full"
      onChange={e =>
        tableData.onFilter(columnId, e.detail.selectedOption?.dataset?.value ?? '')
      }>
      <Option data-value="" selected={currentVal === ''}>
        {t('common.labels.all')}
      </Option>
      <Option data-value="true" selected={currentVal === 'true'}>
        {t('common.labels.yes')}
      </Option>
      <Option data-value="false" selected={currentVal === 'false'}>
        {t('common.labels.no')}
      </Option>
    </Select>
  );
};

export const adminUsersColumns = (
  tableData: PcTableData,
  t: Translate
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('id', t('common.labels.id'), tableData),
  PcInputColumn('username', t('adminUsers.list.username'), tableData),
  PcInputColumn('email', t('adminUsers.list.email'), tableData),
  PcInputColumn('first_name', t('adminUsers.list.firstName'), tableData),
  PcInputColumn('last_name', t('adminUsers.list.lastName'), tableData),
  PcInputColumn('full_name', t('adminUsers.list.fullName'), tableData),
  {
    ...PcInputColumn('is_service_user', t('adminUsers.list.serviceUser'), tableData),
    hAlign: TextAlign.Center,
    Cell: (instance: any) => (instance.row.original.is_service_user ? t('common.labels.yes') : t('common.labels.no')),
    Filter: (data: any) => serviceUserFilter(tableData, data.column.id, t),
  },
  PcDateColumn('created_at', t('common.labels.createdAt'), tableData),
  {
    ...PcInputColumn('roles', t('adminUsers.list.roles'), tableData),
    disableSortBy: true,
    Cell: (instance: any) => instance.row.original.roles?.join(', ') ?? '',
  },
  {
    accessor: '.',
    disableFilters: true,
    disableSortBy: true,
    width: 70,
    Cell: (instance: any) => <PcArrowLink link={`${instance.row.original.id}`} />,
  },
];
