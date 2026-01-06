// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { AnalyticalTableColumnDefinition, Button } from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/show';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

export const myCompletedWorkflowsColumns = (
  tableData: PcTableData,
  userId: string | undefined,
  t: Translate
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('title', t('myWorkflowsTable.workflow'), tableData),
  PcInputColumn('subtitle', t('myWorkflowsTable.subtitle'), tableData),
  PcDateColumn('created_at', t('myWorkflowsTable.createdAt'), tableData),
  PcDateColumn('completed_at', t('myWorkflowsTable.completedAt'), tableData),
  PcInputColumn('id', t('myWorkflowsTable.instanceId'), tableData),

  {
    accessor: '.',
    disableFilters: true,
    disableSortBy: true,
    width: 10,
    Cell: (instance: any) => {
      const data = instance.row.original;
      if (data.completed_tasks?.length === 1) {
        return (
          <Link
            to={`/tasks/completed/${data.id}/${data.completed_tasks[0].id}`}
            className="w-full text-center ">
            <Button icon="show" />
          </Link>
        );
      }
      return '';
    },
  },
];
