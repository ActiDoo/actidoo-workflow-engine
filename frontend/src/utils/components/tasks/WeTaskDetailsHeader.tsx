import React from 'react';
import '@ui5/webcomponents-icons/dist/synchronize';
import '@ui5/webcomponents-icons/dist/begin';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/user-edit';
import { TaskItem } from '@/models/models';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { WeTaskStateIcons } from '@/utils/components/WeStateIcon';
import { PcDateString } from '@/ui5-components';

const WeTaskDetailsHeader: React.FC<{
  task: TaskItem;
  additional?: React.ReactElement;
}> = props => {
  const { task } = { ...props };

  return (
    <div className=" flex gap-16 items-start pt-2 pb-6 border-t-1">
      <WeDetailsTable
        data={[
          { label: 'Id', content: task?.id },
          { label: 'Name', content: task?.name },
          { label: 'Title', content: task?.title },
          {
            label: 'Assigned user',
            content: task?.assigned_user ? <>{`${task.assigned_user.full_name}`}</> : undefined,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: 'State',
            content: task ? (
              <WeTaskStateIcons data={task} showEmptyCircle displayLabel />
            ) : undefined,
          },
          {
            label: 'Created at',
            content: task?.created_at ? <PcDateString val={task.created_at.toString()} /> : null,
          },
          {
            label: 'Completed at',
            content: task?.completed_at ? (
              <PcDateString val={task.completed_at.toString()} />
            ) : null,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          { label: 'Lane', content: task?.lane },

          {
            label: 'Lane roles',
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
            label: 'Lane initiator',
            content: task?.lane_initiator ? 'true' : 'false',
          },
          {
            label: 'Triggered By',
            content: task?.triggered_by ? <>{`${task.triggered_by.full_name}`}</> : undefined,
          },
        ]}
      />
      {props.additional ? props.additional : null}
    </div>
  );
};
export default WeTaskDetailsHeader;
