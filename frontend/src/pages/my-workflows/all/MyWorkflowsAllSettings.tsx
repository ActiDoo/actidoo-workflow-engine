// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  AnalyticalTableColumnDefinition,
  Icon,
  IconDesign,
  TextAlign,
  Button,
} from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';
import { type useTranslation } from '@/i18n';
import '@ui5/webcomponents-icons/dist/status-negative';
import '@ui5/webcomponents-icons/dist/status-positive';
import '@ui5/webcomponents-icons/dist/document-text';

type Translate = ReturnType<typeof useTranslation>['t'];

export const myWorkflowsAllColumns = (
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
  PcInputColumn('id', t('myWorkflowsTable.instanceId'), tableData),
  {
    accessor: '.',
    width: 10,
    disableFilters: true,
    disableSortBy: true,
    Cell: (instance: any) => {
      const data = instance.row.original;
      const canEditTask =
        data.active_tasks?.length === 1 && data.active_tasks[0].assigned_user?.id === userId;

      if (!canEditTask) {
        if (data.completed_tasks?.length === 1) {
          return (
            <Link
              to={`/tasks/completed/${data.id}/${data.completed_tasks[0].id}`}
              className="w-full text-center">
              <Button icon="document-text" className="bg-[#009ba4] border-[#009ba4]" />
            </Link>
          );
        }

        return '';
      }

      // When the workflow definition has been removed, the task is read-only. Use the
      // "show" icon to signal "view" rather than "edit".
      const isReadonly = !!data.is_readonly;

      return (
        <Link
          to={`/tasks/open/${data.id}/${data.active_tasks[0].id}`}
          className="w-full text-center">
          <Button icon={isReadonly ? 'show' : 'edit'} className="bg-[#009ba4] border-[#009ba4]" />
        </Link>
      );
    },
  },
];
