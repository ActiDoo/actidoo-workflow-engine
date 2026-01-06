// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';

import { WeDataKey } from '@/store/generic-data/setup';
import { BusyIndicator } from '@ui5/webcomponents-react';
import { getRequest, resetStateForKey } from '@/store/generic-data/actions';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { useNavigate, useParams } from 'react-router-dom';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { MultipleTasks } from '@/pages/tasks/content/multiple-tasks/MultipleTasks';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';

const TaskContent: React.FC<{ state: WorkflowState }> = props => {
  const { t } = useTranslation();
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const data = useSelector((state: State) => state.data[WeDataKey.MY_USER_TASKS]);
  const userTasks = data?.data?.usertasks;
  const userTasksLoadState = useSelector(
    (state: State) => state.ui.loading[WeDataKey.MY_USER_TASKS]
  );

  const [shouldNavigate, setShouldNavigate] = useState(false);

  useEffect(() => {
    // First let's clear/reset all the old data inside the store with resetStateForKey,
    // so that no old data will be kept (in case a new fetch response will not produce the same parameters)
    // and that there is no time window in which data of the old response will be displayed as the new workflow.
    dispatch(resetStateForKey(WeDataKey.MY_USER_TASKS));
    if (workflowId)
      dispatch(
        getRequest(WeDataKey.MY_USER_TASKS, {
          queryParams: { workflow_instance_id: workflowId },
          params: { state: props.state },
        })
      );
    setShouldNavigate(() => true);
  }, [workflowId]);

  useEffect(() => {
    if (shouldNavigate) {
      if (!userTasksLoadState && userTasks && userTasks.length === 1) {
        // if there's only one, then navigate directly to the detail view (navigate will append the ID to the current URL here)
        navigate(userTasks[0].id);
        setShouldNavigate(() => false);
      }
    }
  }, [userTasks]);

  // if it is a single task, then the useeffect navigates directly to the task
  if (userTasksLoadState || (userTasks && userTasks.length === 1))
    return (
      <div className="flex flex-col w-full h-full items-center justify-center pb-32 gap-2">
        <BusyIndicator active={true} delay={200} />
      </div>
    );

  if (userTasks && userTasks.length > 1) return <MultipleTasks userTasks={userTasks} />;

  return (
    <WeEmptySection
      icon="search"
      title={t('taskContent.notFoundTitle')}
      text={t('taskContent.notFoundText')}
    />
  );
};

export default TaskContent;
