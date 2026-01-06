// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  AnalyticalTableColumnDefinition,
  Icon,
  IconDesign,
  TextAlign,
} from '@ui5/webcomponents-react';
import { PcArrowLink, PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import '@ui5/webcomponents-icons/dist/status-negative';
import '@ui5/webcomponents-icons/dist/status-positive';
import '@ui5/webcomponents-icons/dist/play';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

export const adminWorkflowsColumns = (
  tableData: PcTableData,
  t: Translate
): AnalyticalTableColumnDefinition[] => [
  
  //PcInputColumn('name', 'Name', tableData),
  {
    ...PcInputColumn('title', t('adminTables.workflow'), tableData),
    width: 225
  },
  {
    ...PcInputColumn('subtitle', t('adminTables.subtitle'), tableData),
    minWidth: 150,
  },
  {
    minWidth: 150,
    ...PcInputColumn('id', t('adminTables.id'), tableData)
  },
  {
    ...PcDateColumn('created_at', t('adminTables.createdAt'), tableData),
    width: 150,
  },  
  {
    ...PcInputColumn('created_by.full_name', t('adminTables.createdBy'), tableData),
    minWidth: 150,
    Cell: (instance: any) => {
      const flow = instance.row.original;
      return (<>{flow.created_by?.full_name} ({flow.created_by?.email})</>);
    },
  },
  {
    ...PcInputColumn('name', t('adminTables.internalName'), tableData),
    maxWidth: 220
  },  
  {
    ...PcInputColumn('is_completed', t('adminTables.isCompleted'), tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.is_completed ? (
        <Icon name="status-positive" design={IconDesign.Positive} />
      ) : null,
  },
  {
    ...PcInputColumn('has_task_in_error_state', t('adminTables.hasError'), tableData),
    disableFilters: true,
    width: 70,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.has_task_in_error_state ? (
        <Icon name="status-negative" design={IconDesign.Negative} />
      ) : null,
  },
  {
    disableFilters: true,
    disableSortBy: true,
    accessor: '.',
    width: 30,
    Cell: (instance: any) => <PcArrowLink link={`${instance.row.original.id}`} />,
  },
];
