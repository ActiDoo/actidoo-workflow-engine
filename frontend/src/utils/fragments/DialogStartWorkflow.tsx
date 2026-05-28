// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  BusyIndicator,
  Button,
  ButtonDesign,
  Dialog,
  Icon,
  Input,
  Text,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import type { DialogDomRef } from '@ui5/webcomponents-react';
import React, { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { getRequest, postRequest, resetStateForKey } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { State } from '@/store';
import { createPortal } from 'react-dom';
import { addToast } from '@/store/ui/actions';
import { Link, useNavigate } from 'react-router-dom';
import { WeToastContent } from '@/utils/components/WeToast';
import '@ui5/webcomponents-icons/dist/org-chart';
import '@ui5/webcomponents-icons/dist/pushpin-on';
import '@ui5/webcomponents-icons/dist/pushpin-off';
import '@ui5/webcomponents-icons/dist/course-book';
import { WorkflowState } from '@/models/models';
import { environment } from '@/environment';
import { useTranslation } from '@/i18n';

export const DialogStartWorkflow: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [open, setDialogOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dialogRef = useRef<DialogDomRef>(null);
  const [lockedSize, setLockedSize] = useState<{ height: number; width: number } | null>(null);

  const handleSearchInput = (value: string): void => {
    if (value && !search && dialogRef.current) {
      const rect = dialogRef.current.getBoundingClientRect();
      setLockedSize({ height: rect.height, width: rect.width });
    } else if (!value) {
      setLockedSize(null);
    }
    setSearch(value);
  };

  const workflowData = useSelector((state: State) => state.data[WeDataKey.WORKFLOWS]);
  const startData = useSelector((state: State) => state.data[WeDataKey.START_WORKFLOW]);
  const pinnedData = useSelector((state: State) => state.data[WeDataKey.PINNED_WORKFLOWS]);
  const togglePinData = useSelector((state: State) => state.data[WeDataKey.TOGGLE_PINNED_WORKFLOW]);
  const workflowOptions = workflowData?.data?.workflows;

  const [pinned, setPinned] = useState<string[]>([]);
  const pinnedSet = new Set(pinned);

  const togglePin = (name: string): void => {
    setPinned(prev => (prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]));
    dispatch(postRequest(WeDataKey.TOGGLE_PINNED_WORKFLOW, { name }));
  };

  const buildSearchRegExp = (query: string): RegExp | null => {
    if (!query) return null;
    try {
      return new RegExp(query, 'gi');
    } catch {
      return new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    }
  };

  const matchesSearch = (title: string, query: string): boolean => {
    const regex = buildSearchRegExp(query);
    return regex ? regex.test(title) : true;
  };

  const highlightMatch = (title: string, query: string): React.ReactNode => {
    const regex = buildSearchRegExp(query);
    if (!regex) return title;

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(title)) !== null) {
      if (match[0].length === 0) {
        regex.lastIndex++;
        continue;
      }
      if (match.index > lastIndex) parts.push(title.slice(lastIndex, match.index));
      parts.push(
        <span key={match.index} className="!text-brand-primary !font-bold">
          {match[0]}
        </span>
      );
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex < title.length) parts.push(title.slice(lastIndex));
    return parts.length > 0 ? parts : title;
  };

  const filteredWorkflows = workflowOptions?.filter(w => matchesSearch(w.title, search)) ?? [];
  const sortByTitle = (a: { title: string }, b: { title: string }): number =>
    a.title.localeCompare(b.title, undefined, { sensitivity: 'base' });
  const pinnedGroup = filteredWorkflows.filter(w => pinnedSet.has(w.name)).sort(sortByTitle);
  const restGroup = filteredWorkflows.filter(w => !pinnedSet.has(w.name)).sort(sortByTitle);
  const hasResults = pinnedGroup.length + restGroup.length > 0;

  const closeDialog = (): void => {
    setDialogOpen(false);
    setSearch('');
    setLockedSize(null);
  };

  const loadingState = useSelector((state: State) => state.ui.loading);
  const isLoading =
    loadingState[`${WeDataKey.WORKFLOWS}POST`] || loadingState[`${WeDataKey.START_WORKFLOW}POST`];

  useEffect(() => {
    dispatch(getRequest(WeDataKey.WORKFLOWS));
    dispatch(getRequest(WeDataKey.PINNED_WORKFLOWS));
  }, []);

  useEffect(() => {
    if (pinnedData?.data?.pinned_workflow_names) {
      setPinned(pinnedData.data.pinned_workflow_names);
    }
  }, [pinnedData?.data]);

  useEffect(() => {
    if (togglePinData?.postResponse === 200 && togglePinData.data?.pinned_workflow_names) {
      setPinned(togglePinData.data.pinned_workflow_names);
    }
  }, [togglePinData?.postResponse, togglePinData?.data]);

  useEffect(() => {
    if (startData?.postResponse === 200) {
      dispatch(
        postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state: WorkflowState.READY })
      );
      dispatch(addToast(<WeToastContent type="success" text={t('dialogStartWorkflow.success')} />));
      closeDialog();
      if (startData.data?.workflow_instance_id)
        navigate(`/tasks/open/${startData.data?.workflow_instance_id}`);
    } else if (startData?.postResponse && startData?.postResponse !== 200) {
      dispatch(addToast(<>{t('dialogStartWorkflow.error')}</>));
    }
    dispatch(resetStateForKey(WeDataKey.START_WORKFLOW));
  }, [startData?.postResponse]);

  const environmentInfo =
    // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- empty string is not a valid label, fallback intentional
    environment.environmentLabel ||
    (environment.apiUrl.includes('localhost') ? 'LOCALHOST - TESTING' : '');

  const renderWorkflowRow = (w: { name: string; title: string }): React.ReactNode => {
    const isPinned = pinnedSet.has(w.name);
    return (
      <div
        key={`workflow_${w.name}`}
        className="flex items-center justify-between py-2 pr-4 w-full">
        <div className="flex items-center gap-2">
          <Link to={`workflow-diagram/${w.name}`} onClick={closeDialog} className="inline-flex">
            <Icon name="org-chart" className="!font-bold !text-brand-primary cursor-pointer" />
          </Link>
          <Text>{highlightMatch(w.title, search)}</Text>
        </div>
        <div className="flex items-center gap-3">
          <Icon
            name={isPinned ? 'pushpin-on' : 'pushpin-off'}
            accessibleName={t(isPinned ? 'dialogStartWorkflow.unpin' : 'dialogStartWorkflow.pin')}
            className={`cursor-pointer ${isPinned ? '!text-brand-primary' : ''}`}
            onClick={() => {
              togglePin(w.name);
            }}
          />
          <Text
            className="!font-bold !text-brand-primary cursor-pointer"
            onClick={() => {
              dispatch(postRequest(WeDataKey.START_WORKFLOW, { name: w.name }));
            }}>
            {t('dialogStartWorkflow.start')}
          </Text>
        </div>
      </div>
    );
  };

  return (
    <>
      <span>
        {environmentInfo && (
          <span style={{ color: 'red', paddingRight: 10 }}>{environmentInfo}</span>
        )}
      </span>
      <Button
        design={ButtonDesign.Emphasized}
        icon="add"
        onClick={() => {
          setDialogOpen(true);
        }}>
        {t('dialogStartWorkflow.startWorkflow')}
      </Button>
      {createPortal(
        <Dialog
          ref={dialogRef}
          open={open}
          style={
            lockedSize
              ? {
                  height: `min(${lockedSize.height}px, 94%)`,
                  width: `min(${lockedSize.width}px, 90%)`,
                }
              : undefined
          }
          header={
            <div className="w-full flex items-center gap-2">
              <Title level={TitleLevel.H5} className="w-full py-2">
                {t('dialogStartWorkflow.header')}
              </Title>
              <Icon className="cursor-pointer " name="decline" onClick={closeDialog} />
            </div>
          }>
          {workflowOptions ? (
            <BusyIndicator
              active={isLoading}
              size="Medium"
              delay={0}
              className="bg-white/80 w-full h-full">
              <div className="w-full h-full flex flex-col">
                <Input
                  className="w-full mb-2"
                  icon={
                    <>
                      {search && (
                        <Icon
                          name="decline"
                          className="cursor-pointer -mr-2"
                          onClick={() => {
                            handleSearchInput('');
                          }}
                        />
                      )}
                      <Icon name="search" />
                    </>
                  }
                  placeholder={t('dialogStartWorkflow.searchPlaceholder')}
                  value={search}
                  onInput={e => {
                    handleSearchInput(e.target.value ?? '');
                  }}
                />
                {hasResults ? (
                  <>
                    {pinnedGroup.map(renderWorkflowRow)}
                    {restGroup.map(renderWorkflowRow)}
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center gap-2">
                    <Icon name="course-book" className="!w-4 !h-4 !text-brand-primary" />
                    <Text>{t('dialogStartWorkflow.noneFound')}</Text>
                  </div>
                )}
              </div>
            </BusyIndicator>
          ) : (
            <Text>{t('dialogStartWorkflow.noneFound')}</Text>
          )}
        </Dialog>,
        document.body
      )}
    </>
  );
};
