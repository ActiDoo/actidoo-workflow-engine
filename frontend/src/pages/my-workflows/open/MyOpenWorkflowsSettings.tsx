// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { AnalyticalTableColumnDefinition, Button } from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/show';
import { type useTranslation } from '@/i18n';

type Translate = ReturnType<typeof useTranslation>['t'];

export const myOpenWorkflowsColumns = (
  tableData: PcTableData,
  userId: string | undefined,
  t: Translate,
  onShowSubmittedForm?: (workflowId: string, taskId?: string) => void
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
      const canEditTask =
        data.active_tasks?.length === 1 && data.active_tasks[0].assigned_user?.id === userId;
      const completedTasks =
        data.completed_tasks?.filter(
          (task: any) =>
            task.completed_by_user?.id === userId || task.completed_by_delegate_user?.id === userId
        ) ?? [];
      const completedTask = completedTasks.length === 1 ? completedTasks[0] : null;
      const canShowSubmittedForm =
        completedTasks.length > 0 && typeof onShowSubmittedForm === 'function';

      if (!canEditTask && !canShowSubmittedForm) {
        return '';
      }

      return (
        <div className="flex items-center justify-center gap-2">
          {canShowSubmittedForm ? (
            <Button
              icon="show"
              onClick={() => {
                onShowSubmittedForm?.(data.id, completedTask?.id);
              }}
            />
          ) : null}
          {canEditTask ? (
            <Link
              to={`/tasks/open/${data.id}/${data.active_tasks[0].id}`}
              className="w-full text-center">
              <Button icon="edit" />
            </Link>
          ) : null}
        </div>
      );
    },
  },
];
