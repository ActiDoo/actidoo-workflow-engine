// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import '@ui5/webcomponents-icons/dist/synchronize';
import '@ui5/webcomponents-icons/dist/begin';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/user-edit';
import { TaskItem } from '@/models/models';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { WeTaskStateIcons } from '@/utils/components/WeStateIcon';
import { PcDateString } from '@/ui5-components';
import { useTranslation } from '@/i18n';

const WeTaskDetailsHeader: React.FC<{
  task: TaskItem;
  additional?: React.ReactElement;
}> = props => {
  const { t } = useTranslation();
  const { task } = { ...props };

  return (
    <div className=" flex gap-16 items-start pt-2 pb-6 border-t-1">
      <WeDetailsTable
        data={[
          { label: t('common.labels.id'), content: task?.id },
          { label: t('common.labels.name'), content: task?.name },
          { label: t('common.labels.title'), content: task?.title },
          {
            label: t('common.labels.assignedUser'),
            content: task?.assigned_user ? <>{`${task.assigned_user.full_name}`}</> : undefined,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: t('common.labels.state'),
            content: task ? (
              <WeTaskStateIcons data={task} showEmptyCircle displayLabel />
            ) : undefined,
          },
          {
            label: t('common.labels.createdAt'),
            content: task?.created_at ? <PcDateString val={task.created_at.toString()} /> : null,
          },
          {
            label: t('common.labels.completedAt'),
            content: task?.completed_at ? (
              <PcDateString val={task.completed_at.toString()} />
            ) : null,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          { label: t('common.labels.lane'), content: task?.lane },

          {
            label: t('common.labels.laneRoles'),
            content: task?.lane_roles
              ? task.lane_roles.map((lane, index) => (
                  <>
                    {lane}
                    {task.lane_roles && task.lane_roles.length > index + 1 ? ', ' : '-'}
                  </>
                ))
              : undefined,
          },
          {
            label: t('common.labels.laneInitiator'),
            content: task?.lane_initiator ? t('common.labels.yes') : t('common.labels.no'),
          },
          {
            label: t('common.labels.triggeredBy'),
            content: task?.triggered_by ? <>{`${task.triggered_by.full_name}`}</> : undefined,
          },
        ]}
      />
      {props.additional ? props.additional : null}
    </div>
  );
};
export default WeTaskDetailsHeader;
