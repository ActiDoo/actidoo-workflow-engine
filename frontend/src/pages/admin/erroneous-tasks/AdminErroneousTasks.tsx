// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

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
  PcDynamicPage,
  PcSearch,
  StringDict,
  useAdditionalTableFunctions,
} from '@/ui5-components';
import { environment } from '@/environment';
import { adminTasksColumns } from '@/pages/admin/tasks/AdminTasksSettings';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { useTranslation } from '@/i18n';

const AdminErroneousTasks: React.FC = () => {
  const { t } = useTranslation();
  const key = WeDataKey.ADMIN_ERRONEOUS_TASKS;
  const dispatch = useDispatch();

  const data = useSelector((state: State) => state.data[key]);
  const loadingState = useSelectUiLoading(key, 'POST');
  const [offset, search, filter, sort] = getTableDataFromQueryParams(data?.queryParams);
  const finalFilter: StringDict = {
    ...filter,
    state_error: true,
    workflow_instance___is_completed: false,
  };
  const [tableData] = useAdditionalTableFunctions(
    environment.tableCount,
    offset,
    search,
    finalFilter,
    sort
  );

  useEffect(() => {
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData, environment.tableCount),
        keepData: true,
      })
    );
  }, [tableData.loadData]);

  return (
    <PcDynamicPage
      header={{ title: t('admin.erroneousTasks') }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <div className="flex items-center justify-end w-100 mb-4 gap-2">
        <PcSearch initialSearch={tableData.search} searchInput={tableData.onSearch} />
      </div>
      <PcAnalyticalTable
        columns={adminTasksColumns(tableData, t, '/admin/all-tasks')}
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
      />
    </PcDynamicPage>
  );
};

export default AdminErroneousTasks;
