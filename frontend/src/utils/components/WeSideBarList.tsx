// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useRef, useState } from 'react';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  Icon,
  Input,
  List,
  MessageStrip,
  MessageStripDesign,
  StandardListItem,
  Text,
} from '@ui5/webcomponents-react';
import { useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { useNavigate, useParams } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/activity-2.js';
import '@ui5/webcomponents-icons/dist/search.js';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';
import { useInfiniteWorkflowInstances } from '@/utils/hooks/useInfiniteWorkflowInstances';

interface WeSideBarListProps {
  dataKey: WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS;
  state: WorkflowState;
  errorMessage?: string;
  emptyMessage?: string;
  /** Extra classes for the root element, e.g. responsive width/visibility. */
  className?: string;
}

const SEARCH_DEBOUNCE_MS = 300;

export const WeSideBarList: React.FC<WeSideBarListProps> = props => {
  const { t, language } = useTranslation();
  const { workflowId } = useParams();
  const navigate = useNavigate();

  const currentUserId = useSelector((state: State) => state.data[WeDataKey.WFE_USER]?.data?.id);

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce the search before hitting the backend.
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(handle);
    };
  }, [searchInput]);

  const { items, loadingInitial, loadingMore, error, hasMore, loadMore } =
    useInfiniteWorkflowInstances(props.state, debouncedSearch);

  // Load the next page when the sentinel scrolls into view.
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasMore) return;
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) loadMore();
      },
      { root: null, rootMargin: '200px' }
    );
    observer.observe(node);
    return () => {
      observer.disconnect();
    };
  }, [hasMore, loadMore, loadingMore, items.length]);

  const errorComponent = (
    <MessageStrip className="p-12" design={MessageStripDesign.Negative} hideCloseButton={true}>
      {props.errorMessage ?? t('sidebar.loadingError')}
    </MessageStrip>
  );

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
    <div className={`absolute top-0 bottom-0 overflow-y-auto bg-white ${props.className ?? ''}`}>
      {searchBar}
      {loadingInitial ? (
        <BusyIndicator
          active={true}
          delay={0}
          className="w-full h-full flex items-center justify-center"
        />
      ) : error && items.length === 0 ? (
        errorComponent
      ) : items.length > 0 ? (
        <>
          <List>
            {items.map(instance => {
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
                  <div className="py-2">
                    <Text className={`${isSelected ? '!font-bold' : ''} ml-1 `}>
                      {instance.title}
                    </Text>
                    {instance.subtitle && (
                      <Text className={`!text-xs !text-neutral-700  !block ml-1 `}>
                        {instance.subtitle}
                      </Text>
                    )}
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
          <Text> {props.emptyMessage ?? t('sidebar.noItems')}</Text>
        </div>
      )}
    </div>
  );
};
