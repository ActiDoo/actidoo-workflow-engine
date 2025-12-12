import { AnalyticalTableColumnDefinition, Button } from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';

export const myOpenWorkflowsColumns = (
  tableData: PcTableData,
  userId: string | undefined
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('title', 'Workflow', tableData),
  PcInputColumn('subtitle', 'Subtitle', tableData),
  {
    ...PcInputColumn('active_tasks', 'Active task(s)', tableData),
    Cell: (instance: any) => {
      const flow = instance.row.original;
      if (flow.active_tasks?.length === 1) {
        return <>{flow.active_tasks[0].title}</>;
      } else {
        return `${flow.active_tasks?.length} active tasks`;
      }
    },
  },
  {
    ...PcInputColumn('assigned_user', 'Assigned to', tableData),
    Cell: (instance: any) => {
      const data = instance.row.original;
      if (data.active_tasks?.length === 1) {
        return <>{data.active_tasks[0].assigned_user?.full_name}</>;
      } else {
        return '';
      }
    },
  },
  PcDateColumn('created_at', 'Created at', tableData),
  PcInputColumn('id', 'Instance Id', tableData),
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
