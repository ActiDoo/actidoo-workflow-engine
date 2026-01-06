// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { AnalyticalTableColumnDefinition, Button } from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

export const myOpenWorkflowsColumns = (
  tableData: PcTableData,
  userId: string | undefined,
  t: Translate
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('title', t('myWorkflowsTable.workflow'), tableData),
  PcInputColumn('subtitle', t('myWorkflowsTable.subtitle'), tableData),
  {
    ...PcInputColumn('active_tasks', t('myWorkflowsTable.activeTasks'), tableData),
    Cell: (instance: any) => {
      const flow = instance.row.original;
      if (flow.active_tasks?.length === 1) {
        return <>{flow.active_tasks[0].title}</>;
      } else {
        return t('myWorkflowsTable.activeTaskCount', {
          count: flow.active_tasks?.length ?? 0,
        });
      }
    },
  },
  {
    ...PcInputColumn('assigned_user', t('myWorkflowsTable.assignedTo'), tableData),
    Cell: (instance: any) => {
      const data = instance.row.original;
      if (data.active_tasks?.length === 1) {
        return <>{data.active_tasks[0].assigned_user?.full_name}</>;
      } else {
        return '';
      }
    },
  },
  PcDateColumn('created_at', t('myWorkflowsTable.createdAt'), tableData),
  PcInputColumn('id', t('myWorkflowsTable.instanceId'), tableData),
  {
    accessor: '.',
    width: 10,
    disableFilters: true,
    disableSortBy: true,
    Cell: (instance: any) => {
      const data = instance.row.original;
      if (data.active_tasks?.length === 1 && data.active_tasks[0].assigned_user?.id === userId) {
        return (
          <Link
            to={`/tasks/open/${data.id}/${data.active_tasks[0].id}`}
            className="w-full text-center ">
            <Button icon="edit" />
          </Link>
        );
      }
      return '';
    },
  },
];
