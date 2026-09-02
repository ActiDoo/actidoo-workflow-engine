// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  Dialog,
  List,
  StandardListItem,
  Text,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/org-chart';
import '@ui5/webcomponents-icons/dist/download';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest, resetStateForKey } from '@/store/generic-data/actions';
import {
  calculateInitialPage,
  getQueryParamsFromTableData,
  getTableDataFromQueryParams,
  PcAnalyticalTable,
  PcDynamicPage,
  PcSearch,
  TableQueryParams,
  useAdditionalTableFunctions,
} from '@/ui5-components';
import { environment } from '@/environment';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { buildDataColumns } from '@/pages/data/buildDataColumns';
import { DataActionSchema } from '@/models/dataViewer';
import { useTranslation } from '@/i18n';

interface PendingAction {
  row: Record<string, unknown>;
  action: DataActionSchema;
}

const DataModelTable: React.FC = () => {
  // Remount the table per model: the table-state hook is not resettable, so
  // without the key a filter/sort would silently survive a /data/A → /data/B
  // switch and leak into the other model.
  const { modelName = '' } = useParams<{ modelName: string }>();
  return <DataModelTableInner key={modelName} modelName={modelName} />;
};

const DataModelTableInner: React.FC<{ modelName: string }> = ({ modelName }) => {
  const { t, language } = useTranslation();
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const key = WeDataKey.WORKFLOW_DATA_ROWS;
  const startKey = WeDataKey.START_WORKFLOW_FOR_DATA;

  const data = useSelector((state: State) => state.data[key]);
  const startData = useSelector((state: State) => state.data[startKey]);
  const loadingState = useSelectUiLoading(key); // GET flow keys loading on the bare key
  const actionLoading = useSelectUiLoading(startKey, 'POST');

  const modelLabel = data?.data?.model?.label ?? modelName;

  // The URL is the source of truth for the table state (search/filter/sort/page):
  // F5 keeps the view and a filtered sight is shareable as a link.
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

  // Mirror the table state back into the URL. ``replace`` keeps the browser
  // history clean — paging/filtering must not bury the back button. No limit
  // argument → no LIMIT in the URL.
  useEffect(() => {
    const params = getQueryParamsFromTableData(tableData);
    setSearchParams(
      Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])),
      { replace: true }
    );
  }, [tableData.loadData]);

  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  // ID column display: compact by default, toggleable to the full value (header icon).
  const [showFullIds, setShowFullIds] = useState(false);

  const loadRows = (): void => {
    dispatch(
      getRequest(key, {
        params: { modelName },
        queryParams: getQueryParamsFromTableData(tableData, environment.tableCount),
        keepData: true,
      })
    );
  };

  // The rows store key is shared across models; drop the previous model's rows
  // and columns when switching so they don't briefly flash before the reload.
  useEffect(() => {
    dispatch(resetStateForKey(key));
  }, [modelName]);

  // ``language`` reloads so the server-resolved labels follow a language switch.
  useEffect(() => {
    loadRows();
  }, [tableData.loadData, modelName, language]);

  // Follow-up workflow start: navigate straight to the new instance on success.
  useEffect(() => {
    if (startData?.postResponse === 200) {
      dispatch(addToast(<WeToastContent type="success" text={t('data.startSuccess')} />));
      setPendingAction(null);
      const newInstanceId = startData.data?.workflow_instance_id;
      if (newInstanceId) navigate(`/tasks/open/${newInstanceId}`);
    } else if (startData?.postResponse && startData.postResponse !== 200) {
      dispatch(addToast(<WeToastContent type="error" text={t('data.startError')} />));
    }
    if (startData?.postResponse) dispatch(resetStateForKey(startKey));
  }, [startData?.postResponse]);

  const rows = (data?.data?.ITEMS ?? []).map(item => ({ ...item.data, __actions: item.actions }));
  const fields = data?.data?.model?.fields ?? [];
  // Stable per model (declared actions) — the column must not appear/disappear
  // with the loaded page. Row-derived fallback until the backend field arrives.
  const hasActions =
    data?.data?.model?.has_actions ??
    rows.some(r => Array.isArray(r.__actions) && r.__actions.length > 0);
  // Size the actions column by its content instead of a fixed width.
  const maxActionChars = rows.reduce(
    (max, r) =>
      Math.max(
        max,
        ((r.__actions ?? []) as DataActionSchema[]).reduce((sum, a) => sum + a.label.length, 0)
      ),
    0
  );
  const actionsWidth = Math.min(340, Math.max(140, maxActionChars * 8 + 48));

  // "Involved processes" picker: the workflows that use this model and that the
  // current user may start (a model can be touched by several workflows).
  const [processesOpen, setProcessesOpen] = useState(false);
  const processesKey = WeDataKey.WORKFLOW_DATA_PROCESSES;
  const processes = useSelector((state: State) => state.data[processesKey])?.data ?? [];
  const processesLoading = useSelectUiLoading(processesKey);

  const openProcesses = (): void => {
    // The store key is shared across models; drop the previous model's processes
    // so a stale list never flashes while the current model's fetch is in flight.
    dispatch(resetStateForKey(processesKey));
    dispatch(getRequest(processesKey, { params: { modelName } }));
    setProcessesOpen(true);
  };

  const columns = buildDataColumns(
    fields,
    tableData,
    t,
    language,
    {
      modelName,
      onAction: (row, action) => {
        setPendingAction({ row, action });
      },
      showFullIds,
      onToggleIdDisplay: () => setShowFullIds(full => !full),
    },
    hasActions,
    actionsWidth
  );

  const confirmAction = (): void => {
    if (!pendingAction || actionLoading) return;
    dispatch(
      postRequest(startKey, {
        model_name: modelName,
        id: pendingAction.row.id,
        action: pendingAction.action.key,
      })
    );
  };

  // The export matches the visible view: same filter/search/sort params as the
  // listing, but never paginated (OFFSET stripped; backend ignores pagination).
  const csvQuery = ((): string => {
    const params = getQueryParamsFromTableData(tableData);
    delete params[TableQueryParams.OFFSET];
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))
    ).toString();
    return qs ? `?${qs}` : '';
  })();
  const csvUrl = `${environment.apiUrl}user/workflow-data/${encodeURIComponent(
    modelName
  )}/export.csv${csvQuery}`;

  return (
    <PcDynamicPage
      header={{
        title: modelLabel,
        showBack: true,
        forceBackTo: '/data',
        actionSection: (
          <div className="flex gap-2">
            <Button icon="org-chart" design={ButtonDesign.Transparent} onClick={openProcesses}>
              {t('data.processes')}
            </Button>
            <Button
              icon="download"
              design={ButtonDesign.Transparent}
              onClick={() => window.open(csvUrl)}>
              {t('data.exportCsv')}
            </Button>
          </div>
        ),
      }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <div className="flex items-center justify-end w-100 mb-4 gap-2">
        <PcSearch initialSearch={tableData.search} searchInput={tableData.onSearch} />
      </div>
      <PcAnalyticalTable
        columns={columns}
        initialPage={calculateInitialPage(tableData.offset, environment.tableCount)}
        data={rows}
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
      {createPortal(
        <Dialog
          open={!!pendingAction}
          headerText={t('data.confirmStartHeader')}
          // UI5 closes itself on ESC; sync the React state or reopening is a no-op.
          onAfterClose={() => setPendingAction(null)}>
          <div className="flex flex-col gap-4 p-2">
            <Text>{t('data.confirmStartText', { label: pendingAction?.action.label ?? '' })}</Text>
            <div className="flex justify-end gap-2">
              <Button
                design={ButtonDesign.Transparent}
                disabled={actionLoading}
                onClick={() => {
                  setPendingAction(null);
                }}>
                {t('data.cancel')}
              </Button>
              <BusyIndicator active={!!actionLoading} delay={0}>
                <Button
                  design={ButtonDesign.Emphasized}
                  disabled={!!actionLoading}
                  onClick={confirmAction}>
                  {t('data.start')}
                </Button>
              </BusyIndicator>
            </div>
          </div>
        </Dialog>,
        document.body
      )}
      {createPortal(
        <Dialog
          open={processesOpen}
          headerText={t('data.processesHeader')}
          // UI5 closes itself on ESC; sync the React state or reopening is a no-op.
          onAfterClose={() => setProcessesOpen(false)}
          footer={
            <div className="w-full flex justify-end mt-2">
              <Button onClick={() => setProcessesOpen(false)}>{t('common.actions.close')}</Button>
            </div>
          }>
          <div className="flex flex-col gap-3 p-2 min-w-80 max-w-md">
            {/* Plain-language intro: users otherwise don't understand what this list is. */}
            <Text className="text-neutral-700">{t('data.processesInfo')}</Text>
            {processesLoading ? (
              <BusyIndicator active className="self-center py-4" />
            ) : processes.length === 0 ? (
              <Text>{t('data.processesEmpty')}</Text>
            ) : (
              <List>
                {processes.map(process => (
                  <StandardListItem
                    key={process.name}
                    icon="org-chart"
                    description={t('data.openDiagramHint')}
                    onClick={() => {
                      setProcessesOpen(false);
                      navigate(`/workflow-diagram/${process.name}`);
                    }}>
                    {process.title}
                  </StandardListItem>
                ))}
              </List>
            )}
          </div>
        </Dialog>,
        document.body
      )}
    </PcDynamicPage>
  );
};

export default DataModelTable;
