// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// List of the number ranges (ADR 012) the user may see. One row per range; the
// trailing arrow opens the range's detail page with its scopes and the
// allocation log. The backend decides what the user may see.

import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { AnalyticalTableColumnDefinition, Label, TextAlign } from '@ui5/webcomponents-react';

import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest } from '@/store/generic-data/actions';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { PcAnalyticalTable, PcArrowLink, PcDynamicPage } from '@/ui5-components';
import { PcDateString } from '@/ui5-components/utils/PcDateString';
import { useTranslation } from '@/i18n';
import { NumberRangeSummary } from '@/models/models';

const AdminNumberRanges: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const key = WeDataKey.ADMIN_GET_NUMBER_RANGES;
  const data = useSelector((state: State) => state.data[key]);
  const loading = useSelectUiLoading(key);

  useEffect(() => {
    dispatch(getRequest(key, {}));
  }, [dispatch, key]);

  const ranges: NumberRangeSummary[] = data?.data?.ranges ?? [];
  const loaded = data?.response !== undefined;

  const rows = ranges.map(range => ({
    name: range.name,
    table: range.table,
    workflows: range.workflows.join(', '),
    scopes: range.scopes.length,
    count: range.scopes.reduce((sum, scope) => sum + scope.count, 0),
    last_issued_at: range.scopes
      .map(scope => scope.last_issued_at)
      .filter((value): value is string => value !== null)
      .sort()
      .at(-1),
  }));

  const columns: AnalyticalTableColumnDefinition[] = [
    { Header: t('numberRanges.range'), accessor: 'name' },
    { Header: t('numberRanges.workflows'), accessor: 'workflows' },
    { Header: t('numberRanges.scopes'), accessor: 'scopes', hAlign: TextAlign.End },
    { Header: t('numberRanges.issued'), accessor: 'count', hAlign: TextAlign.End },
    {
      Header: t('numberRanges.lastIssued'),
      accessor: 'last_issued_at',
      Cell: ({ value }: { value?: string }) => <PcDateString val={value} />,
    },
    { Header: t('numberRanges.table'), accessor: 'table' },
    {
      accessor: '.',
      disableFilters: true,
      disableSortBy: true,
      width: 70,
      hAlign: TextAlign.Center,
      Cell: (instance: any) => (
        <PcArrowLink link={encodeURIComponent(instance.row.original.name)} />
      ),
    },
  ];

  return (
    <PcDynamicPage
      header={{ title: t('numberRanges.title') }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <Label className="mb-2">{t('numberRanges.intro')}</Label>
      <PcAnalyticalTable
        columns={columns}
        data={rows}
        loading={!!loading || !loaded}
        response={data?.response}
        noDataText={t('numberRanges.noRanges')}
      />
    </PcDynamicPage>
  );
};

export default AdminNumberRanges;
