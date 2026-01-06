// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import { List, StandardListItem, Text, Title, TitleLevel } from '@ui5/webcomponents-react';
import { WeTaskStateIcons } from '@/utils/components/WeStateIcon';
import WeEditableDataSection from '@/utils/components/WeEditableDataSection';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import '@ui5/webcomponents-icons/dist/activity-items.js';
import { TaskItem } from '@/models/models';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import { useParams } from 'react-router-dom';
import WeTaskDetailsHeader from '@/utils/components/tasks/WeTaskDetailsHeader';
import WeTaskHeaderActions from '@/utils/components/tasks/WeTaskHeaderActions';
import { useTranslation } from '@/i18n';

const AdminWorkflowDetailsTasksSection: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workflowId } = useParams();

  const [selectedTask, setSelectedTask] = useState<TaskItem | undefined>(undefined);
  const [tasks, setSelectedTasks] = useState<TaskItem[] | undefined>(undefined);
  const data = useSelector((state: State) => state.data[WeDataKey.ADMIN_TASKS_OF_WORKFLOW]);

  useEffect(() => {
    getTaskForWorkflow();
  }, []);

  useEffect(() => {
    setSelectedTasks(() => (data?.data?.ITEMS ? [...data.data?.ITEMS].reverse() : undefined));
    if (selectedTask) {
      setSelectedTask(data?.data?.ITEMS?.find(t => t.id === selectedTask.id));
    }
  }, [data?.data?.ITEMS]);

  const getTaskForWorkflow = (): void => {
    dispatch(
      postRequest(WeDataKey.ADMIN_TASKS_OF_WORKFLOW, {}, undefined, {
        f_workflow_instance___id: workflowId,
      })
    );
  };

  return (
    <>
      <div className="bg-white mb-1 pc-px-responsive py-2">
        <Title level={TitleLevel.H4}>{t('admin.tasksHeadline')}</Title>
      </div>
      <div className="flex gap-1 min-w-[200px]">
        <div className="flex-1">
          <List
            onItemClick={event => {
              setSelectedTask(() => tasks?.find(t => t.id === event.detail.item.id));
            }}>
            {tasks?.map(task => (
              <StandardListItem
                key={task.id}
                id={task.id}
                selected={selectedTask?.id === task.id}
                className="pc-pl-responsive">
                <div className="flex items-center gap-2">
                  <div className="inline-block w-4">
                    <WeTaskStateIcons data={task} showEmptyCircle />
                  </div>
                  <Text>{task.title}</Text>
                </div>
              </StandardListItem>
            ))}
          </List>
        </div>
        <div className="flex-[3] bg-white p-4">
          {selectedTask ? (
            <>
              <div className="flex gap-4 justify-between items-center mb-2">
                <Title level={TitleLevel.H4}>{selectedTask?.title}</Title>
                <div>
                  <WeTaskHeaderActions taskId={selectedTask.id} data={selectedTask} />
                </div>
              </div>
              <WeTaskDetailsHeader task={selectedTask} />

              {selectedTask.error_stacktrace ? (
                <>
                  <Title level={TitleLevel.H6}>{t('admin.errorMessage')}</Title>
                  <div className="grid overflow-auto">
                    <pre className="bg-neutral-50 p-2 mb-6 mt-2 rounded ">
                      {selectedTask.error_stacktrace}
                    </pre>
                  </div>
                </>
              ) : null}
              <Title level={TitleLevel.H6}>{t('admin.data')}</Title>

              <WeEditableDataSection
                taskId={selectedTask.id}
                data={selectedTask?.data}
                key={selectedTask.id}
              />
            </>
          ) : (
            <WeEmptySection
              icon="activity-items"
              title={t('admin.noSelectedTaskTitle')}
              text={t('admin.noSelectedTaskText')}
            />
          )}
        </div>
      </div>
    </>
  );
};

export default AdminWorkflowDetailsTasksSection;
