import { AnalyticalTableColumnDefinition, Button } from '@ui5/webcomponents-react';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { Link } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/show';

export const myCompletedWorkflowsColumns = (
  tableData: PcTableData,
  userId: string | undefined
): AnalyticalTableColumnDefinition[] => [
  PcInputColumn('title', 'Workflow', tableData),
  PcInputColumn('subtitle', 'Subtitle', tableData),
  PcDateColumn('created_at', 'Created at', tableData),
  PcDateColumn('completed_at', 'Completed at', tableData),
  PcInputColumn('id', 'Instance Id', tableData),

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
