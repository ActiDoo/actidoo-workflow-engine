// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Detail page of one number range (ADR 012): the state of each scope and the
// allocation log linking every issued number to the workflow instance that
// received it. The table state lives in the URL, like on the data model pages.

import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams, useSearchParams } from 'react-router-dom';
import { AnalyticalTable, InputType, Label, Title, TitleLevel } from '@ui5/webcomponents-react';

import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest, resetStateForKey } from '@/store/generic-data/actions';
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

const AdminNumberRangeDetails: React.FC = () => {
  // Remount per range: the table-state hook is not resettable, so without the
  // key a filter or page would survive a switch between two ranges.
  const { rangeName = '' } = useParams<{ rangeName: string }>();
  return <AdminNumberRangeDetailsInner key={rangeName} rangeName={rangeName} />;
};

const AdminNumberRangeDetailsInner: React.FC<{ rangeName: string }> = ({ rangeName }) => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const rangesKey = WeDataKey.ADMIN_GET_NUMBER_RANGES;
  const key = WeDataKey.ADMIN_GET_NUMBER_RANGE_ALLOCATIONS;

  const ranges = useSelector((state: State) => state.data[rangesKey]);
  const allocations = useSelector((state: State) => state.data[key]);
  const loadingState = useSelectUiLoading(key, 'POST');

  // The URL is the source of truth for the table state, so F5 keeps the view.
  const [searchParams, setSearchParams] = useSearchParams();
  const [offset, search, filter, sort] = getTableDataFromQueryParams(
    Object.fromEntries(searchParams)
  );
  const [tableData] = useAdditionalTableFunctions(
    environment.tableCount,
    offset,
    search,
    filter,
    sort
  );

  useEffect(() => {
    const params = getQueryParamsFromTableData(tableData);
    setSearchParams(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])), {
      replace: true,
    });
  }, [tableData.loadData]);

  useEffect(() => {
    if (ranges?.data === undefined) dispatch(getRequest(rangesKey, {}));
  }, []);

  // The allocations store key is shared across ranges: drop the previous
  // range's log so it does not flash before the reload.
  useEffect(() => {
    dispatch(resetStateForKey(key));
  }, [rangeName]);

  const rangeList: NumberRangeSummary[] = ranges?.data?.ranges ?? [];
  const range = rangeList.find(r => r.name === rangeName) ?? null;
  const rangesLoaded = ranges?.data !== undefined;

  // Load the log only for a range the user may see; an unknown name would
  // just produce a 404 from the backend.
  useEffect(() => {
    if (range === null) return;
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData, environment.tableCount),
        range_name: rangeName,
        keepData: true,
      })
    );
  }, [tableData.loadData, rangeName, range === null]);

  const scopeOf = (scopeKey: string) =>
    scopeKey === '' ? t('numberRanges.globalScope') : scopeKey;

  return (
    <PcDynamicPage
      header={{ title: rangeName, showBack: true, forceBackTo: '/admin/number-ranges' }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      {rangesLoaded && range === null ? (
        <Label>{t('numberRanges.notFound')}</Label>
      ) : (
        <>
          <Title level={TitleLevel.H5} className="mb-2">
            {t('numberRanges.scopes')}
          </Title>
          {range !== null && range.scopes.length === 0 ? (
            <Label className="mb-4">{t('numberRanges.noScopes')}</Label>
          ) : (
            <AnalyticalTable
              className="mb-4"
              minRows={1}
              columns={[
                { Header: t('numberRanges.scope'), accessor: 'scope_key' },
                { Header: t('numberRanges.issued'), accessor: 'count' },
                { Header: t('numberRanges.lastNumber'), accessor: 'last_formatted' },
                {
                  Header: t('numberRanges.lastIssued'),
                  accessor: 'last_issued_at',
                  Cell: ({ value }: { value: string }) => <PcDateString val={value} />,
                },
              ]}
              data={(range?.scopes ?? []).map(scope => ({
                ...scope,
                scope_key: scopeOf(scope.scope_key),
              }))}
            />
          )}

          <div className="flex items-center justify-between w-100 mb-4 gap-2">
            <Title level={TitleLevel.H5}>{t('numberRanges.allocations')}</Title>
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

export default AdminNumberRangeDetails;
