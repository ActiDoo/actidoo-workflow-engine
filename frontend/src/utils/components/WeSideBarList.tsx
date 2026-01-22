// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import {
  BusyIndicator,
  Icon,
  List,
  MessageStrip,
  MessageStripDesign,
  StandardListItem,
  Text,
} from '@ui5/webcomponents-react';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { useNavigate, useParams } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/activity-2.js';
import { postRequest } from '@/store/generic-data/actions';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';

interface WeSideBarListProps {
  dataKey: WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS;
  state: WorkflowState;
  errorMessage?: string;
  emptyMessage?: string;
}

export const WeSideBarList: React.FC<WeSideBarListProps> = props => {
  const { t, language } = useTranslation();
  const { workflowId } = useParams();
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const [error, setError] = useState(false);

  const data = useSelector((state: State) => state.data[props.dataKey]);
  const isLoading = useSelector((state: State) => state.ui.loading[`${props.dataKey}POST`]);
  const currentUserId = useSelector(
    (state: State) => state.data[WeDataKey.WFE_USER]?.data?.id
  );

  useEffect(() => {
    dispatch(postRequest(props.dataKey, {}, { state: props.state }));
  }, []);

  useEffect(() => {
    if (data?.postResponse && data?.postResponse !== 200) {
      setError(true);
    } else if (data?.postResponse === 200) {
      setError(false);
    }
  }, [data?.postResponse]);

  const loadingComponent = (
    <BusyIndicator
      active={isLoading}
      delay={0}
      className="w-full h-full flex items-center justify-center"
    />
  );

  const errorComponent = (
    <MessageStrip className="p-12" design={MessageStripDesign.Negative} hideCloseButton={true}>
      {props.errorMessage ?? t('sidebar.loadingError')}
    </MessageStrip>
  );

  return (
    <div className="absolute top-0 bottom-0 overflow-y-auto bg-white w-[280px]">
      {isLoading ? (
        loadingComponent
      ) : error ? (
        errorComponent
      ) : data?.data?.ITEMS && data.data.ITEMS.length > 0 ? (
        <List>
          {data?.data?.ITEMS.map(instance => {
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
                className={` h-auto pc-pl-responsive ${isDelegationHighlight ? 'bg-orange-50' : ''}`}
                key={`task-item-${instance.id}`}
                onClick={() => {
                  navigate(`${instance.id}`);
                }}>
                <div className="py-2">
                  <Text className={`${isSelected ? '!font-bold' : ''} ml-1 `}>{instance.title}</Text>
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
                      {t('taskContent.delegateActingFor')} {delegationTask.assigned_user.full_name}
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
      ) : (
        <div className="p-12 flex items-center gap-2">
          <Icon name="activity-2" />
          <Text> {props.emptyMessage ?? t('sidebar.noItems')}</Text>
        </div>
      )}
    </div>
  );
};
