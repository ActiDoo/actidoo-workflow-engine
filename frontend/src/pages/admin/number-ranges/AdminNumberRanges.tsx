// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Read-only view of number ranges (ADR 012): which workflows declare a range,
// the state of each of its scopes, and the allocation log linking every issued
// number to the workflow instance that received it. The backend decides what
// the user may see; this page shows what comes back.

import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { AnalyticalTable, InputType, Label } from '@ui5/webcomponents-react';

import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { useSelectUiLoading } from '@/store/ui/selectors';
import {
  PcAnalyticalTable,
  PcDateColumn,
  PcDynamicPage,
  PcInputColumn,
  PcSearch,
  PcTableData,
} from '@/ui5-components';
import { PcDateString } from '@/ui5-components/utils/PcDateString';
import { useAdditionalTableFunctions } from '@/ui5-components/hooks/useAdditionalTableFunctions';
import {
  calculateInitialPage,
  getQueryParamsFromTableData,
  getTableDataFromQueryParams,
} from '@/ui5-components/services/PageService';
import { environment } from '@/environment';
import { useTranslation } from '@/i18n';
import { NumberRangeSummary } from '@/models/models';

const allocationColumns = (tableData: PcTableData, t: ReturnType<typeof useTranslation>['t']) => [
  PcInputColumn('formatted', t('numberRanges.number'), tableData),
  PcInputColumn('scope_key', t('numberRanges.scope'), tableData),
  PcInputColumn('value', t('numberRanges.sequence'), tableData, InputType.Number),
  PcDateColumn('created_at', t('numberRanges.issuedAt'), tableData),
  PcInputColumn('alloc_key', t('numberRanges.draw'), tableData),
  PcInputColumn('workflow_instance_task_id', t('numberRanges.step'), tableData),
  PcInputColumn('workflow_instance_id', t('numberRanges.instance'), tableData, undefined, {
    pre: '/admin/all-workflows/',
    parts: [{ value: 'workflow_instance_id', isInstanceValue: true }],
  }),
];

const AdminNumberRanges: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const key = WeDataKey.ADMIN_GET_NUMBER_RANGE_ALLOCATIONS;

  const ranges = useSelector((state: State) => state.data[WeDataKey.ADMIN_GET_NUMBER_RANGES]);
  const allocations = useSelector((state: State) => state.data[key]);
  const loadingState = useSelectUiLoading(key, 'POST');

  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [offset, search, filter, sort] = getTableDataFromQueryParams(allocations?.queryParams);
  const [tableData] = useAdditionalTableFunctions(
    environment.tableCount,
    offset,
    search,
    filter,
    sort
  );

  useEffect(() => {
    dispatch(getRequest(WeDataKey.ADMIN_GET_NUMBER_RANGES, {}));
  }, []);

  useEffect(() => {
    if (selectedName === null) return;
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData, environment.tableCount),
        range_name: selectedName,
        keepData: true,
      })
    );
  }, [selectedName, tableData.loadData]);

  const rangeList: NumberRangeSummary[] = ranges?.data?.ranges ?? [];
  const selected = useMemo(
    () => rangeList.find(r => r.name === selectedName) ?? null,
    [rangeList, selectedName]
  );

  const scopeOf = (scopeKey: string) =>
    scopeKey === '' ? t('numberRanges.globalScope') : scopeKey;
  const overviewRows = rangeList.flatMap(range =>
    range.scopes.length === 0
      ? [{ name: range.name, table: range.table, workflows: range.workflows.join(', ') }]
      : range.scopes.map(scope => ({
          name: range.name,
          table: range.table,
          workflows: range.workflows.join(', '),
          scope_key: scopeOf(scope.scope_key),
          count: scope.count,
          last_formatted: scope.last_formatted,
          last_issued_at: scope.last_issued_at,
        }))
  );

  return (
    <PcDynamicPage
      header={{ title: t('numberRanges.title') }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <Label className="mb-2">{t('numberRanges.intro')}</Label>

      {ranges?.data !== undefined && rangeList.length === 0 ? (
        <Label>{t('numberRanges.noRanges')}</Label>
      ) : (
        <AnalyticalTable
          className="mb-4"
          minRows={1}
          selectionMode="SingleSelect"
          onRowSelect={event => {
            const row = event?.detail?.row?.original as { name?: string } | undefined;
            if (row?.name) {
              setSelectedName(row.name);
              tableData.onPageClick(0);
            }
          }}
          columns={[
            { Header: t('numberRanges.range'), accessor: 'name' },
            { Header: t('numberRanges.workflows'), accessor: 'workflows' },
            { Header: t('numberRanges.scope'), accessor: 'scope_key' },
            { Header: t('numberRanges.issued'), accessor: 'count' },
            { Header: t('numberRanges.lastNumber'), accessor: 'last_formatted' },
            {
              Header: t('numberRanges.lastIssued'),
              accessor: 'last_issued_at',
              Cell: ({ value }: { value: string }) => <PcDateString val={value} />,
            },
            { Header: t('numberRanges.table'), accessor: 'table' },
          ]}
          data={overviewRows}
        />
      )}

      {selected === null ? (
        <Label>{t('numberRanges.selectRange')}</Label>
      ) : (
        <>
          <div className="flex items-center justify-between w-100 mb-4 gap-2">
            <Label>{t('numberRanges.allocationsOf', { name: selected.name })}</Label>
            <PcSearch initialSearch={tableData.search} searchInput={tableData.onSearch} />
          </div>
          <PcAnalyticalTable
            columns={allocationColumns(tableData, t)}
            initialPage={calculateInitialPage(tableData.offset, environment.tableCount)}
            data={(allocations?.data?.ITEMS ?? []).map(item => ({
              ...item,
              scope_key: scopeOf(item.scope_key),
            }))}
            loading={loadingState}
            response={allocations?.response}
            pageChange={tableData.onPageClick}
            filter={tableData.filter}
            sort={tableData.sort}
            onSort={tableData.onSort}
            itemsCount={allocations?.data?.COUNT}
            limit={environment.tableCount}
            forcePage={tableData.forcePage}
            filterable={true}
          />
        </>
      )}
    </PcDynamicPage>
  );
};

export default AdminNumberRanges;
