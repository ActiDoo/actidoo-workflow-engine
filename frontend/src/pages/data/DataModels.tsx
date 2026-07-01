// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { AnalyticalTableColumnDefinition, TextAlign } from '@ui5/webcomponents-react';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest } from '@/store/generic-data/actions';
import { PcAnalyticalTable, PcArrowLink, PcDynamicPage } from '@/ui5-components';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { useTranslation } from '@/i18n';

const DataModels: React.FC = () => {
  const { t, language } = useTranslation();
  const dispatch = useDispatch();
  const key = WeDataKey.WORKFLOW_DATA_MODELS;
  const data = useSelector((state: State) => state.data[key]);
  const loading = useSelectUiLoading(key);

  // ``language`` reloads so the server-resolved labels follow a language switch.
  useEffect(() => {
    dispatch(getRequest(key));
  }, [dispatch, key, language]);

  const models = data?.data ?? [];
  // Distinguish "still loading" from "loaded, but empty": only fall back to the
  // empty state once a response has actually arrived.
  const loaded = data?.response !== undefined;

  const columns: AnalyticalTableColumnDefinition[] = [
    {
      accessor: 'label',
      Header: t('data.modelName'),
      Cell: (instance: any) => {
        const model = instance.row.original;
        return <span>{model.label ?? model.name}</span>;
      },
    },
    {
      accessor: 'row_count',
      Header: t('data.rowCount'),
      hAlign: TextAlign.End,
      Cell: (instance: any) => (
        <span className="tabular-nums">{instance.row.original.row_count ?? ''}</span>
      ),
    },
    {
      // Trailing arrow opening the model's row table (idiom shared with the admin/
      // statistics list pages and the data row table).
      accessor: '.',
      disableFilters: true,
      disableSortBy: true,
      width: 70,
      hAlign: TextAlign.Center,
      Cell: (instance: any) => <PcArrowLink link={`/data/${instance.row.original.name}`} />,
    },
  ];

  return (
    <PcDynamicPage
      header={{ title: t('data.modelsTitle') }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <PcAnalyticalTable
        columns={columns}
        data={models}
        loading={!!loading || !loaded}
        response={data?.response}
        noDataText={t('data.noModels')}
      />
    </PcDynamicPage>
  );
};

export default DataModels;
