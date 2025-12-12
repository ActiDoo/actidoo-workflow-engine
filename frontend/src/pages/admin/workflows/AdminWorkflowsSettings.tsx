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
import { right } from '@popperjs/core';

export const adminWorkflowsColumns = (
  tableData: PcTableData
): AnalyticalTableColumnDefinition[] => [
  
  //PcInputColumn('name', 'Name', tableData),
  {
    ...PcInputColumn('title', 'Workflow', tableData),
    width: 225
  },
  {
    ...PcInputColumn('subtitle', 'Subtitle', tableData),
    minWidth: 150,
  },
  {
    minWidth: 150,
    ...PcInputColumn('id', 'Id', tableData)
  },
  {
    ...PcDateColumn('created_at', 'Created at', tableData),
    width: 150,
  },  
  {
    ...PcInputColumn('created_by.full_name', 'Created by', tableData),
    minWidth: 150,
    Cell: (instance: any) => {
      const flow = instance.row.original;
      return (<>{flow.created_by?.full_name} ({flow.created_by?.email})</>);
    },
  },
  {
    ...PcInputColumn('name', 'Internal Name', tableData),
    maxWidth: 220
  },  
  {
    ...PcInputColumn('is_completed', 'Completed', tableData),
    disableFilters: true,
    width: 90,
    hAlign: TextAlign.Center,
    Cell: (instance: any) =>
      instance.row.original.is_completed ? (
        <Icon name="status-positive" design={IconDesign.Positive} />
      ) : null,
  },
  {
    ...PcInputColumn('has_task_in_error_state', 'Error', tableData),
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
