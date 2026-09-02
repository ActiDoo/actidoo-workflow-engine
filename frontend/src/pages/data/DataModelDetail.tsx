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
  Link,
  List,
  MessageStrip,
  MessageStripDesign,
  StandardListItem,
  Text,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/history';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest, resetStateForKey } from '@/store/generic-data/actions';
import { PcDynamicPage } from '@/ui5-components';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { DataActionSchema } from '@/models/dataViewer';
import { FormatFieldCtx, formatFieldValue } from '@/pages/data/formatFieldValue';
import { useTranslation } from '@/i18n';

const shortId = (id: string): string => id.slice(0, 8);

const DataModelDetail: React.FC = () => {
  const { t, language } = useTranslation();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { modelName = '', recordId = '' } = useParams<{ modelName: string; recordId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const key = WeDataKey.WORKFLOW_DATA_VERSION_CHAIN;
  const startKey = WeDataKey.START_WORKFLOW_FOR_DATA;
  const chainState = useSelector((state: State) => state.data[key]);
  const chain = chainState?.data;
  const startData = useSelector((state: State) => state.data[startKey]);
  const loading = useSelectUiLoading(key);
  const actionLoading = useSelectUiLoading(startKey, 'POST');

  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [pendingAction, setPendingAction] = useState<DataActionSchema | null>(null);

  // The store key is shared; drop the previous record before loading the new one.
  useEffect(() => {
    dispatch(resetStateForKey(key));
    setSelectedIndex(null);
    dispatch(getRequest(key, { params: { modelName, recordId } }));
  }, [modelName, recordId, language]);

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

  // Distinguish "still loading" from "loaded": only judge the payload once a
  // response actually arrived (same guard as the models list).
  const loaded = chainState?.response !== undefined;
  const versions = chain?.versions ?? [];
  const fields = chain?.model?.fields ?? [];
  const modelLabel = chain?.model?.label ?? modelName;
  const actions = (chain?.actions ?? []) as DataActionSchema[];
  const headIndex = versions.length - 1; // endpoint returns oldest-first → head is last
  const idx = selectedIndex ?? headIndex;
  const selected = versions[idx];
  const isHead = idx === headIndex;

  // Record identity in the header — from the head version, so the page title does
  // not jump while browsing the history. Falls back to the short id when the
  // record carries no title.
  const head = versions[headIndex];
  const recordTitle = head ? String(head.data?.title ?? shortId(recordId)) : null;
  const pageTitle = recordTitle ? `${modelLabel}: ${recordTitle}` : modelLabel;

  // Version selection with URL mirroring (?version=N, replace so the browser back
  // button never steps through version states).
  const selectVersion = (i: number): void => {
    if (i === headIndex) {
      setSelectedIndex(null);
      setSearchParams({}, { replace: true });
    } else {
      setSelectedIndex(i);
      const versionNo = versions[i]?.data?.version;
      setSearchParams({ version: String(versionNo ?? i) }, { replace: true });
    }
  };

  // Deep link: apply ?version=N once the chain arrived.
  useEffect(() => {
    const v = searchParams.get('version');
    if (!v || versions.length === 0) return;
    const i = versions.findIndex(x => String(x.data?.version) === v);
    if (i >= 0 && i !== headIndex) {
      setSelectedIndex(i);
      setHistoryOpen(true);
    }
  }, [chain]);

  const formatDate = (iso: string | null): string =>
    iso ? new Date(iso).toLocaleString(language) : '';

  const ctxFor = (versionData: Record<string, unknown>): FormatFieldCtx => ({
    modelName,
    language,
    t,
    recordId,
    version: versionData?.version,
  });

  const confirmAction = (): void => {
    if (!pendingAction || actionLoading) return;
    dispatch(
      postRequest(startKey, { model_name: modelName, id: recordId, action: pendingAction.key })
    );
  };

  // Actions act on the current record, so they are only offered while viewing the head.
  const headActions = isHead ? actions : [];

  const toggleHistory = (): void => {
    setHistoryOpen(open => {
      // Closing the panel returns to the current version — otherwise the user is
      // stuck on an old version with no visible way back.
      if (open) selectVersion(headIndex);
      return !open;
    });
  };

  return (
    <PcDynamicPage
      header={{
        title: pageTitle,
        showBack: true,
        forceBackTo: `/data/${encodeURIComponent(modelName)}`,
        actionSection: (
          <div className="flex gap-2">
            {headActions.map(action => (
              <Button
                key={action.key}
                design={ButtonDesign.Transparent}
                onClick={() => setPendingAction(action)}>
                {action.label}
              </Button>
            ))}
            {versions.length > 1 && (
              <Button icon="history" design={ButtonDesign.Transparent} onClick={toggleHistory}>
                {t('data.history')}
              </Button>
            )}
          </div>
        ),
      }}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      {loading || !loaded ? (
        <BusyIndicator active className="self-center mt-8" />
      ) : chainState?.response !== 200 ? (
        <MessageStrip design={MessageStripDesign.Negative} hideCloseButton className="block">
          {t('table.loadingError')}
        </MessageStrip>
      ) : !selected ? (
        <Text>{t('data.notFound')}</Text>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4 lg:items-start">
          <div className="flex-1 min-w-0">
            {!isHead && (
              <MessageStrip
                design={MessageStripDesign.Information}
                hideCloseButton
                className="mb-4 block">
                {t('data.viewingOldVersion', { date: formatDate(selected.created_at) })}{' '}
                {t('data.actionsOnlyOnCurrent')}{' '}
                <Link onClick={() => selectVersion(headIndex)}>{t('data.backToCurrent')}</Link>
              </MessageStrip>
            )}
            <div className="bg-white rounded-lg shadow-sm p-6 space-y-3">
              {fields.map(field => (
                <div key={field.name} className="flex gap-4">
                  <div className="w-48 shrink-0 text-neutral-700">{field.label}</div>
                  <div className="flex-1 min-w-0 break-words">
                    {formatFieldValue(field, selected.data[field.name], ctxFor(selected.data))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {historyOpen && (
            <div className="w-full lg:w-80 lg:shrink-0 bg-white rounded-lg shadow-sm flex flex-col lg:sticky lg:top-4 max-h-[70vh]">
              <div className="px-3 py-2 border-b border-border-subtle font-bold">
                {t('data.historyPanelTitle', { count: String(versions.length) })}
              </div>
              <div className="overflow-y-auto">
                <List>
                  {versions
                    .map((_, i) => versions.length - 1 - i) // newest first
                    .map(realIdx => {
                      const v = versions[realIdx];
                      const isHeadEntry = realIdx === headIndex;
                      return (
                        <StandardListItem
                          key={realIdx}
                          className="h-auto"
                          selected={realIdx === idx}
                          onClick={() => selectVersion(realIdx)}>
                          <div className="py-1">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate">{formatDate(v.created_at)}</span>
                              {isHeadEntry && (
                                <span className="text-xs text-brand-primary shrink-0">
                                  {t('data.currentVersion')}
                                </span>
                              )}
                            </div>
                            {v.action && (
                              <div className="text-xs text-neutral-700">
                                {t('data.versionAction.' + v.action, v.action)}
                              </div>
                            )}
                          </div>
                        </StandardListItem>
                      );
                    })}
                </List>
              </div>
            </div>
          )}
        </div>
      )}

      {createPortal(
        <Dialog
          open={!!pendingAction}
          headerText={t('data.confirmStartHeader')}
          // UI5 closes itself on ESC; sync the React state or reopening is a no-op.
          onAfterClose={() => setPendingAction(null)}>
          <div className="flex flex-col gap-4 p-2">
            <Text>{t('data.confirmStartText', { label: pendingAction?.label ?? '' })}</Text>
            <div className="flex justify-end gap-2">
              <Button
                design={ButtonDesign.Transparent}
                disabled={actionLoading}
                onClick={() => setPendingAction(null)}>
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
    </PcDynamicPage>
  );
};

export default DataModelDetail;
