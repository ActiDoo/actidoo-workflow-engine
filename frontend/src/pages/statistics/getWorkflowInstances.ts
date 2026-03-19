// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { State } from '@/store';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import {
  getTableDataFromQueryParams,
  useAdditionalTableFunctions,
  getQueryParamsFromTableData,
} from '@/ui5-components';
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';

export function WorkflowInstancesData() {
  const key = WeDataKey.ADMIN_GRAPH_OBJECTS;
  const dispatch = useDispatch();
  const data = useSelector((state: State) => state.data[key]);
  const wfInstances = data?.data?.ITEMS ?? [];
  const [offset, search, filter, sort] = getTableDataFromQueryParams(data?.queryParams);
  const [tableData] = useAdditionalTableFunctions(300, offset, search, filter, sort);

  useEffect(() => {
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData),
        keepData: true,
      })
    );
  }, [tableData.loadData]);
  return wfInstances;
}
