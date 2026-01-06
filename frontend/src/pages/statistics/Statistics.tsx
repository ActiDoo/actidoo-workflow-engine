// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import '@/pages/tasks/Tasks.scss';
import { PcArrowLink, PcPage } from '@/ui5-components';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest } from '@/store/generic-data/actions';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { AnalyticalTable } from '@ui5/webcomponents-react';
import { WorkflowInstancesData } from './getWorkflowInstances';
import { createCountforWFs } from './utils/formatWfs';
import { filterWorkflows, mergeByTitle } from './utils/workflowUtils';
import Graph, { Workflow } from './utils/Graph';
import { DateSelection } from './utils/Datepicker';
import { useTranslation } from '@/i18n';

const Statistics: React.FC = () => {
  const { t } = useTranslation();
  const key = WeDataKey.WORKFLOW_STATISTICS;
  const dispatch = useDispatch();

  const [endDate, setEndDate] = useState<Date>(new Date());
  const [startDate, setStartDate] = useState<Date>(new Date(new Date().setFullYear(new Date().getFullYear() - 1)));
  const filteredWFs = mergeByTitle(filterWorkflows(WorkflowInstancesData()));
  const graph_data: [Workflow] | any = [];


  filteredWFs.forEach(workflow => {
    const result = createCountforWFs(workflow.title, workflow.dates, startDate, endDate);
    graph_data.push(result);
  });

  const data = useSelector((state: State) => state.data[key]);

  useEffect(() => {
    dispatch(getRequest(key));
  }, []);

  return (
    <PcPage
      header={{
        title: t('statistics.title')
      }}>
      <Graph workflows={graph_data} startSetter={setStartDate} endSetter={setEndDate} startDate={startDate} endDate={endDate} />

      <AnalyticalTable
        className='mb-4'
        columns={[
          {
            Header: t('common.labels.title'),
            accessor: 'title'
          },
          {
            Header: t('statistics.activeInstances'),
            accessor: 'active_instances'
          },
          {
            Header: t('statistics.completedInstances'),
            accessor: 'completed_instances',
          },
          {
            Header: t('statistics.estimatedInstancesPerYear'),
            accessor: 'estimated_instances_per_year'
          },
          {
            Header: t('statistics.estimatedSavingsPerYear'),
            accessor: 'estimated_savings_per_year'
          }
        ]}
        minRows={1}
        data={[
          {
            title: t('statistics.sumForAll'),
            active_instances: (data?.data?.workflows || []).reduce(
              (sum, item) => sum + item.active_instances,
              0
            ),
            completed_instances: (data?.data?.workflows || []).reduce(
              (sum, item) => sum + item.completed_instances,
              0
            ),
            //"estimated_saved_mins_per_instance": (data?.data?.workflows || []).reduce((sum, item) => sum + item.active_instances, 0),
            estimated_instances_per_year: (data?.data?.workflows || []).reduce(
              (sum, item) => sum + item.estimated_instances_per_year,
              0
            ),
            estimated_savings_per_year: (data?.data?.workflows || []).reduce(
              (sum, item) => sum + item.estimated_savings_per_year,
              0
            ),
          },
        ]}
      />

      <AnalyticalTable
        columns={[
          {
            Header: t('common.labels.title'),
            accessor: 'title'
          },
          {
            Header: t('statistics.activeInstances'),
            accessor: 'active_instances'
          },
          {
            Header: t('statistics.completedInstances'),
            accessor: 'completed_instances',
          },
          {
            Header: t('statistics.estimatedSavingsPerInstance'),
            accessor: 'estimated_saved_mins_per_instance'
          },
          {
            Header: t('statistics.estimatedInstancesPerYear'),
            accessor: 'estimated_instances_per_year'
          },
          {
            Header: t('statistics.estimatedSavingsPerYear'),
            accessor: 'estimated_savings_per_year'
          },
          {
            Header: '',
            accessor: '.',
            disableFilters: true,
            disableSortBy: true,
            width: 70,
            Cell: (instance: any) => <PcArrowLink link={`/statistics/overview/${instance.row.original.name}`} />
          }
        ]}
        data={data?.data?.workflows || []}
        visibleRowCountMode="Auto"
      />
    </PcPage>
  );
};

export default Statistics;
