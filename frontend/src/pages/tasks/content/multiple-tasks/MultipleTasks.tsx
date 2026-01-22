// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { Icon, Text, Title, TitleLevel } from '@ui5/webcomponents-react';
import { UserTask } from '@/models/models';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '@/i18n';

interface MultipleTaskListProps {
  userTasks: UserTask[];
}
export const MultipleTasks: React.FC<MultipleTaskListProps> = props => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <div className="flex items-center justify-center h-full m-4 pb-24">
      <div className="flex flex-col gap-2 ">
        <div className="text-center mb-4 ">
          <Title level={TitleLevel.H3}>{t('taskContent.multipleAvailable')}</Title>
        </div>
        {props.userTasks.map(task => {
          const isDelegated = task.assigned_to_me_as_delegate;
          return (
            <div
              key={task.id}
              className={`p-4 flex items-center gap-2 cursor-pointer hover:shadow-sm transition-all rounded ${
                isDelegated ? 'bg-orange-50 border-l-4 border-orange-400' : 'bg-white'
              }`}
              onClick={() => {
                navigate(task.id);
              }}>
              <Text className="flex-1">
                {task.name}
                <div className="text-sm text-neutral-400">
                  {isDelegated && task.assigned_user
                    ? `${t('taskContent.delegateActingFor')} ${task.assigned_user.full_name}`
                    : task.assigned_user
                    ? `${task.assigned_user.full_name}`
                    : t('taskContent.unassigned')}
                </div>
                {isDelegated ? (
                  <div className="text-xs text-orange-700">{t('taskContent.delegatedBadge')}</div>
                ) : null}
              </Text>
              <Icon name="navigation-right-arrow" />
            </div>
          );
        })}
      </div>
    </div>
  );
};
