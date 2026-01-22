// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { AnalyticalTableColumnDefinition, TextAlign } from '@ui5/webcomponents-react';
import { PcArrowLink, PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';

import {
  WeStateCanceledIcon,
  WeStateCompletedIcon,
  WeStateErrorIcon,
  WeStateReadyIcon,
} from '@/utils/components/WeStateIcon';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

export const adminTasksColumns = (
  tableData: PcTableData,
  t: Translate
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('workflow_instance.title', t('adminTables.workflow'), tableData),
  PcInputColumn('workflow_instance.subtitle', t('adminTables.subtitle'), tableData),
  PcInputColumn('workflow_instance.id', t('adminTables.wfInstanceId'), tableData),

  PcInputColumn('id', t('adminTables.taskId'), tableData),
  PcInputColumn('lane', t('adminTables.lane'), tableData),
  PcInputColumn('title', t('adminTables.taskName'), tableData),
  PcDateColumn('created_at', t('adminTables.createdAt'), tableData),
  PcDateColumn('completed_at', t('adminTables.completedAt'), tableData),
  {
    ...PcInputColumn('assigned_user.full_name', t('adminTables.assignedTo'), tableData),
    Cell: (instance: any) => {
      const flow = instance.row.original;
      if (flow.assigned_user) {
        return <>{flow.assigned_user?.full_name}</>;
      } else {
        return flow.active_tasks?.length;
      }
    },
  },
  {
    ...PcInputColumn(
      'assigned_delegate_user.full_name',
      t('adminTables.assignedDelegate'),
      tableData
    ),
    Cell: (instance: any) => instance.row.original.assigned_delegate_user?.full_name ?? '',
  },
  {
    ...PcInputColumn('state_cancelled', t('adminTables.canceled'), tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.state_cancelled ? <WeStateCanceledIcon /> : null,
  },
  {
    ...PcInputColumn('state_completed', t('adminTables.completed'), tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.state_completed ? <WeStateCompletedIcon /> : null,
  },
  {
    ...PcInputColumn('state_error', t('adminTables.error'), tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) => (instance.row.original.state_error ? <WeStateErrorIcon /> : null),
  },
  {
    ...PcInputColumn('state_ready', t('adminTables.ready'), tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) => (instance.row.original.state_ready ? <WeStateReadyIcon /> : null),
  },
  {
    accessor: '.',
    disableFilters: true,
    disableSortBy: true,
    width: 70,
    Cell: (instance: any) => <PcArrowLink link={`${instance.row.original.id}`} />,
  },
];
