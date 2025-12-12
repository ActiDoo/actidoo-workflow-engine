import React from 'react';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { WeStateCompletedIcon, WeStateErrorIcon } from '@/utils/components/WeStateIcon';
import { AdminWorkflowInstance } from '@/models/models';

const AdminWorkflowDetailsHeader: React.FC<{ workflow?: AdminWorkflowInstance }> = props => {
  const { workflow } = { ...props };
  return (
    <div className=" flex gap-16 items-start pb-2">
      <WeDetailsTable
        data={[
          { label: 'Id', content: workflow?.id },
          { label: 'Name', content: workflow?.name },
        ]}
      />
      <WeDetailsTable
        data={[
          { label: 'Title', content: workflow?.title },
          {
            label: 'Subtitle',
            content: workflow?.subtitle,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: 'Is completed',
            content: workflow?.is_completed ? <WeStateCompletedIcon /> : '',
          },
          {
            label: 'Has task in error state',
            content: workflow?.has_task_in_error_state ? <WeStateErrorIcon /> : '',
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: 'Created by',
            content: workflow?.created_by ? <>{workflow.created_by.full_name}</> : '',
          },
        ]}
      />
    </div>
  );
};

export default AdminWorkflowDetailsHeader;
