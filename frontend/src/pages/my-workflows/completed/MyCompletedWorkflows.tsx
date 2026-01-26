// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect } from 'react';

import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import {
  calculateInitialPage,
  getQueryParamsFromTableData,
  getTableDataFromQueryParams,
  PcAnalyticalTable,
  StringDict,
  useAdditionalTableFunctions,
  PcSearch,
} from '@/ui5-components';
import { environment } from '@/environment';
import { myCompletedWorkflowsColumns } from '@/pages/my-workflows/completed/MyCompletedWorkflowsSettings';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { ActiveTaskInstance } from '@/models/models';
import { WeTaskSubRow } from '@/utils/components/WeTaskSubRow';
import { useTranslation } from '@/i18n';

const MyCompletedWorkflows: React.FC = () => {
  const { t } = useTranslation();
  const key = WeDataKey.MY_COMPLETED_WORKFLOW_INSTANCES;
  const dispatch = useDispatch();

  const data = useSelector((state: State) => state.data[key]);
  const user = useSelector((state: State) => state.data[WeDataKey.WFE_USER])?.data;
  const loadingState = useSelectUiLoading(key, 'POST');
  const [offset, search, filter, sort] = getTableDataFromQueryParams(data?.queryParams);
  const finalFilter: StringDict = { ...filter, is_completed: true };
  const [tableData] = useAdditionalTableFunctions(
    Number(environment.tableCount),
    offset,
    search,
    finalFilter,
    sort
  );

  const renderRowSubComponent = (row: any): React.ReactElement | null => {
    const completedTasks: ActiveTaskInstance[] | undefined = row.original.completed_tasks;
    if (completedTasks && completedTasks.length > 1) {
      return (
        <WeTaskSubRow
          title={t('myWorkflows.tasksOfWorkflow')}
          tasks={completedTasks}
          userId={user?.id}
          workflowId={row.original.id}
        />
      );
    }
    return null;
  };

  useEffect(() => {
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData, Number(environment.tableCount)),
        keepData: true,
      })
    );
  }, [tableData.loadData]);

  return (
    <>
      <div className="flex items-center justify-end w-100 mb-4 gap-2 -mt-4">
        <PcSearch initialSearch={search} searchInput={tableData.onSearch} />
      </div>

      <div className="my-workflows-table">
        <PcAnalyticalTable
          columns={myCompletedWorkflowsColumns(tableData, user?.id, t)}
          initialPage={calculateInitialPage(tableData.offset, environment.tableCount)}
          data={data?.data?.ITEMS ?? []}
          loading={loadingState}
          response={data?.response}
          pageChange={tableData.onPageClick}
          filter={tableData.filter}
          sort={tableData.sort}
          onSort={tableData.onSort}
          itemsCount={data?.data?.COUNT}
          limit={environment.tableCount}
          forcePage={tableData.forcePage}
          filterable={true}
          renderRowSubComponent={renderRowSubComponent}
        />
      </div>
    </>
  );
};

export default MyCompletedWorkflows;
