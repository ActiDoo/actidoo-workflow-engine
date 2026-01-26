// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { Button, Text, Title, TitleLevel } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/show';
import { useTranslation } from '@/i18n';
import { ActiveTaskInstance } from '@/models/models';

export const WeCompletedTaskSubRow: React.FC<{
  title: string;
  tasks: ActiveTaskInstance[];
  onShowForm: (taskId: string) => void;
}> = props => {
  const { t } = useTranslation();

  return (
    <div className="bg-white border-t border-t-solid border-t-neutral-100 p-3 pb-6">
      <Title className="mb-2" level={TitleLevel.H5}>
        {props.title}
      </Title>

      <table className="text-left w-full border-t border-t-solid border-t-neutral-100">
        <thead>
          <tr>
            <th className="px-2 py-1">{t('common.labels.name')}</th>
            <th className="px-2 py-1">{t('common.labels.completedBy')}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {props.tasks?.map((task, index) => {
            const completedBy =
              task.completed_by_user?.full_name ??
              task.completed_by_delegate_user?.full_name ??
              task.assigned_user?.full_name ??
              '';

            return (
              <tr key={task.id} className={index % 2 === 0 ? 'bg-neutral-50' : ''}>
                <td className="p-2 py-1">
                  <Text>{task.title ?? task.name}</Text>
                </td>
                <td className="p-2 py-1">
                  <Text>{completedBy}</Text>
                </td>
                <td className="p-2 py-1 text-right">
                  <Button icon="show" onClick={() => props.onShowForm(task.id)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
