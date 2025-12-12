import { AnalyticalTableColumnDefinition, TextAlign } from '@ui5/webcomponents-react';
import { PcArrowLink, PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';

import {
  WeStateCanceledIcon,
  WeStateCompletedIcon,
  WeStateErrorIcon,
  WeStateReadyIcon,
} from '@/utils/components/WeStateIcon';

export const adminTasksColumns = (tableData: PcTableData): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('workflow_instance.title', 'Workflow', tableData),
  PcInputColumn('workflow_instance.subtitle', 'Subtitle', tableData),
  PcInputColumn('workflow_instance.id', 'Wf Instance Id', tableData),

  PcInputColumn('id', 'Task Id', tableData),  
  PcInputColumn('lane', 'Lane', tableData),
  PcInputColumn('title', 'Task name', tableData),
  PcDateColumn('created_at', 'Created at', tableData),
  PcDateColumn('completed_at', 'Completed at', tableData),
  {
    ...PcInputColumn('assigned_user.full_name', 'Assigned to', tableData),
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
    ...PcInputColumn('state_cancelled', 'Canceled', tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.state_cancelled ? <WeStateCanceledIcon /> : null,
  },
  {
    ...PcInputColumn('state_completed', 'Completed', tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.state_completed ? <WeStateCompletedIcon /> : null,
  },
  {
    ...PcInputColumn('state_error', 'Error', tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) => (instance.row.original.state_error ? <WeStateErrorIcon /> : null),
  },
  {
    ...PcInputColumn('state_ready', 'Ready', tableData),
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
