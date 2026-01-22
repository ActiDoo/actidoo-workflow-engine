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
  PcPage,
  useAdditionalTableFunctions,
} from '@/ui5-components';
import { environment } from '@/environment';
import { adminUsersColumns } from '@/pages/admin/users/AdminUsersSettings';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { useTranslation } from '@/i18n';

const AdminUsers: React.FC = () => {
  const { t } = useTranslation();
  const key = WeDataKey.ADMIN_ALL_USERS;
  const dispatch = useDispatch();

  const data = useSelector((state: State) => state.data[key]);
  const loadingState = useSelectUiLoading(key, 'POST');
  const [offset, search, filter, sort] = getTableDataFromQueryParams(data?.queryParams);
  const [tableData] = useAdditionalTableFunctions(
    environment.tableCount,
    offset,
    search,
    filter,
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
    <PcPage
      header={{
        title: t('admin.users'),
        initialSearch: tableData.search,
        searchInput: tableData.onSearch,
      }}>
      <PcAnalyticalTable
        columns={adminUsersColumns(tableData, t)}
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
    </PcPage>
  );
};

export default AdminUsers;
