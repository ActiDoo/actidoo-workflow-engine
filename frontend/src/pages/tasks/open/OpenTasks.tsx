import React, { Suspense } from 'react';
import { Outlet, useParams } from 'react-router-dom';

import '@ui5/webcomponents-icons/dist/activity-items.js';
import { WeSideBarList } from '@/utils/components/WeSideBarList';
import { WeDataKey } from '@/store/generic-data/setup';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { WorkflowState } from '@/models/models';

const OpenTasks: React.FC = () => {
  const { workflowId } = useParams();
  
  const isStartWorkflowPreview = window.location.pathname.includes('start_workflow_preview');

  return (
    <div className="flex ">
      <WeSideBarList
        dataKey={WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS}
        state={WorkflowState.READY}
        emptyMessage="You don't have any open tasks"
      />
      <div className="absolute top-0 bottom-0 overflow-y-auto left-[280px] right-0 bottom-0 ">
        {(workflowId || isStartWorkflowPreview) ? (
          <Suspense>
            <Outlet />
          </Suspense>
        ) : (
          <WeEmptySection
            icon="activity-items"
            title="No task selected"
            text="Select task on the left side"
          />
        )}
      </div>
    </div>
  );
};

export default OpenTasks;
