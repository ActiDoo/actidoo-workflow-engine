// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  Icon,
  Input,
  List,
  MessageStrip,
  MessageStripDesign,
  ResponsivePopover,
  StandardListItem,
  Text,
  type ResponsivePopoverDomRef,
} from '@ui5/webcomponents-react';
import { useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { useNavigate, useParams } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/activity-2.js';
import '@ui5/webcomponents-icons/dist/message-information.js';
import '@ui5/webcomponents-icons/dist/accept.js';
import '@ui5/webcomponents-icons/dist/search.js';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';
import { useInfiniteWorkflowInstances } from '@/utils/hooks/useInfiniteWorkflowInstances';
import { getTaskPriorityMeta } from '@/utils/taskPrioritySettings';
import {
  TASK_PRIORITY_CRITICAL_COLOR,
  TASK_PRIORITY_URGENT_COLOR,
  WePriorityClock,
} from '@/utils/components/WePriorityClock';

interface WeSideBarListProps {
  dataKey: WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS;
  state: WorkflowState;
  errorMessage?: string;
  emptyMessage?: string;
  /** Extra classes for the root element, e.g. responsive width/visibility. */
  className?: string;
}
const SEARCH_DEBOUNCE_MS = 300;
const COMPLETED_COLOR = '#09AE3B';

export const WeSideBarList: React.FC<WeSideBarListProps> = props => {
  const { t, language } = useTranslation();
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const [infoContent, setInfoContent] = useState<{
    title?: string;
    subtitle?: string;
    startDate?: string;
    worfkFlowID: string;
  } | null>(null);

  const infoPopoverRef = useRef<ResponsivePopoverDomRef | null>(null);

  const currentUserId = useSelector((state: State) => state.data[WeDataKey.WFE_USER]?.data?.id);

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const CompletedIcon = () => (
    <Icon
      name="accept"
      className="inline-block !h-[1em] !w-[1em] shrink-0 align-[-0.12em]"
      style={{ color: COMPLETED_COLOR }}
    />
  );

  // Debounce the search before hitting the backend.
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(handle);
    };
  }, [searchInput]);

  const { items, loadingInitial, loadingMore, error, hasMore, loadMore, reload } =
    useInfiniteWorkflowInstances(props.dataKey, props.state, debouncedSearch);

  const sortedItems = useMemo(() => {
    if (props.state === WorkflowState.COMPLETED) return items;

    return [...items].sort((first, second) => {
      const firstMeta = getTaskPriorityMeta({
        deadline: first.deadline,
        priorityDate: first.priority_date,
        createdAt: first.created_at,
      });
      const secondMeta = getTaskPriorityMeta({
        deadline: second.deadline,
        priorityDate: second.priority_date,
        createdAt: second.created_at,
      });

      if (firstMeta.priority !== secondMeta.priority) {
        return secondMeta.priority - firstMeta.priority;
      }
      if (firstMeta.priority > 0 && firstMeta.referenceTime !== secondMeta.referenceTime) {
        return firstMeta.referenceTime - secondMeta.referenceTime;
      }
      return 0;
    });
  }, [items, props.state]);

  // Load the next page when the sentinel scrolls into view. The observer root is
  // the sidebar's own scroll container — with the viewport as root the 200px
  // prefetch margin would never apply inside the overflow container.
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = sentinelRef.current;
    // On error the observer detaches: retries happen only via the buttons —
    // otherwise a persistent backend error becomes an unthrottled request loop.
    if (!node || !hasMore || error || loadingMore || loadingInitial) return;
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) loadMore();
      },
      { root: containerRef.current, rootMargin: '200px' }
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, [hasMore, error, loadMore, loadingMore, loadingInitial, sortedItems.length]);

  const errorComponent = (
    <div className="p-12 flex flex-col items-center gap-3">
      <MessageStrip design={MessageStripDesign.Negative} hideCloseButton={true}>
        {props.errorMessage ?? t('sidebar.loadingError')}
      </MessageStrip>
      <Button
        design={ButtonDesign.Transparent}
        onClick={() => {
          reload();
        }}>
        {t('sidebar.retry')}
      </Button>
    </div>
  );

  const formatDateTime = (value?: string | Date | null) => {
    if (!value) return undefined;

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return undefined;

    return new Intl.DateTimeFormat(language === 'de' ? 'de-DE' : language, {
      dateStyle: 'medium',
    }).format(date);
  };

  const searchBar = (
    <div className="sticky top-0 z-10 bg-white p-2 border-b border-neutral-200">
      <Input
        className="w-full"
        value={searchInput}
        placeholder={t('sidebar.searchPlaceholder')}
        showClearIcon={true}
        icon={<Icon name="search" />}
        onInput={e => {
          setSearchInput(e.target.value ?? '');
        }}
      />
    </div>
  );

  const renderBottom = () => {
    if (loadingMore) {
      return (
        <div className="py-4 flex items-center justify-center">
          <BusyIndicator active={true} delay={0} />
        </div>
      );
    }
    if (error && items.length > 0) {
      return (
        <div className="p-3 flex flex-col items-center gap-2">
          <Text className="!text-xs !text-red-700">{t('sidebar.loadMoreError')}</Text>
          <Button
            design={ButtonDesign.Transparent}
            onClick={() => {
              loadMore();
            }}>
            {t('sidebar.loadMore')}
          </Button>
        </div>
      );
    }
    if (hasMore) {
      return (
        <div className="py-3 flex items-center justify-center">
          <Button
            design={ButtonDesign.Transparent}
            onClick={() => {
              loadMore();
            }}>
            {t('sidebar.loadMore')}
          </Button>
        </div>
      );
    }
    return null;
  };

  return (
    <div
      ref={containerRef}
      className={`absolute top-0 bottom-0 overflow-y-auto bg-white ${props.className ?? ''}`}>
      {searchBar}
      <ResponsivePopover ref={infoPopoverRef} headerText={infoContent?.title} placementType="Right">
        <div className="flex flex-col">
          {infoContent?.startDate && (
            <div className="flex flex-col gap-1 mb-4">
              <Text className="!text-xs !font-bold !text-neutral-700">
                {t('sidebar.startDate')}
              </Text>
              <Text className="!text-xs !text-neutral-600">{infoContent.startDate}</Text>
            </div>
          )}
          <div className="flex flex-col gap-1 !max-w-[250px] !break-words mb-4">
            <Text className="!text-xs !font-bold !text-neutral-700">Subtitle</Text>
            <Text className="!text-xs !text-neutral-600">{infoContent?.subtitle ?? '-'}</Text>
          </div>
          {infoContent?.worfkFlowID && (
            <div className="flex flex-col gap-1">
              <Text className="!text-xs !font-bold !text-neutral-700">
                {t('sidebar.workFlowInstanceID')}
              </Text>
              <Text className="!text-xs !text-neutral-600">{infoContent?.worfkFlowID}</Text>
            </div>
          )}
        </div>
      </ResponsivePopover>
      {loadingInitial ? (
        <BusyIndicator
          active={true}
          delay={0}
          className="w-full h-full flex items-center justify-center"
        />
      ) : error && sortedItems.length === 0 ? (
        errorComponent
      ) : sortedItems.length > 0 ? (
        <>
          <List>
            {sortedItems.map(instance => {
              const isSelected = workflowId === instance.id.toString();
              const tasks =
                props.state === WorkflowState.COMPLETED
                  ? instance.completed_tasks
                  : instance.active_tasks;
              const delegationTask =
                currentUserId && tasks
                  ? tasks.find(task => {
                      const assignedUserId = task.assigned_user?.id;
                      const assignedToOther =
                        assignedUserId !== undefined && assignedUserId !== currentUserId;
                      if (!assignedToOther) return false;
                      const delegateIsMe = task.assigned_delegate_user?.id === currentUserId;
                      return delegateIsMe || !!task.can_be_assigned_as_delegate;
                    })
                  : undefined;
              const isDelegationHighlight = !!delegationTask;
              const priorityMeta = getTaskPriorityMeta({
                deadline: instance.deadline,
                priorityDate: instance.priority_date,
                createdAt: instance.created_at,
              });
              const taskCount = tasks?.length ?? 0;
              const suffix = taskCount > 1 ? (language === 'de' ? 'n' : 's') : '';
              const taskLabel =
                taskCount > 1
                  ? t('sidebar.taskCount', { count: taskCount, suffix })
                  : `${t('common.labels.task')}:`;
              return (
                <StandardListItem
                  className={` h-auto pc-pl-responsive ${
                    isDelegationHighlight ? 'bg-orange-50' : ''
                  }`}
                  key={`task-item-${instance.id}`}
                  onClick={() => {
                    navigate(`${instance.id}`);
                  }}>
                  <div className="py-3 w-full">
                    <div className="flex items-start justify-between gap-2 ml-1 pr-5">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1 min-w-0">
                          <Text className={`${isSelected ? '!font-bold' : ''} !mb-0`}>
                            {instance.title}
                          </Text>
                          {props.state === WorkflowState.COMPLETED ? (
                            <CompletedIcon />
                          ) : priorityMeta.level === 'critical' ? (
                            <WePriorityClock hour={20} color={TASK_PRIORITY_CRITICAL_COLOR} />
                          ) : priorityMeta.level === 'urgency' ? (
                            <WePriorityClock hour={16} color={TASK_PRIORITY_URGENT_COLOR} />
                          ) : null}
                        </div>

                        {instance.subtitle && (
                          <Text className="!text-xs !text-neutral-700 !block ml-1">
                            {instance.subtitle}
                          </Text>
                        )}
                      </div>
                      <Icon
                        name="message-information"
                        accessibleName="Mehr Informationen"
                        className="!w-4 !h-4 relative top-2"
                        onClick={event => {
                          event.stopPropagation();
                          setInfoContent({
                            title: instance.title,
                            subtitle: instance.subtitle ?? undefined,
                            startDate: formatDateTime(instance.created_at),
                            worfkFlowID: instance.id,
                          });
                          void infoPopoverRef.current?.showAt(event.currentTarget, true);
                        }}
                      />
                    </div>
                    {tasks && tasks.length > 0 && (
                      <Text className={`!text-xs !text-neutral-700 !block ml-1 `}>
                        <div className="line-clamp-1">
                          {taskLabel}
                          {tasks.map((task, index: number) => (
                            <span key={`taskname-${instance.id}-${index}`}>
                              {task.title}
                              {tasks && tasks.length > index + 1 ? ', ' : ''}
                            </span>
                          ))}
                        </div>
                      </Text>
                    )}
                    {isDelegationHighlight && delegationTask?.assigned_user?.full_name ? (
                      <Text className="!text-xs !text-orange-800 !block ml-1 mt-1">
                        {t('taskContent.delegateActingFor')}{' '}
                        {delegationTask.assigned_user.full_name}
                      </Text>
                    ) : null}
                  </div>
                  {isSelected ? (
                    <div className="bg-brand-primary w-1 absolute right-0 top-0.5 bottom-0.5"></div>
                  ) : (
                    ''
                  )}
                </StandardListItem>
              );
            })}
          </List>
          <div ref={sentinelRef} aria-hidden="true" className="h-px" />
          {renderBottom()}
        </>
      ) : (
        <div className="p-12 flex items-center gap-2">
          <Icon name="activity-2" />
          <Text>
            {' '}
            {debouncedSearch
              ? t('sidebar.noSearchResults')
              : props.emptyMessage ?? t('sidebar.noItems')}
          </Text>
        </div>
      )}
    </div>
  );
};
