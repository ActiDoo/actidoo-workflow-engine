// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';
import { Outlet, useParams } from 'react-router-dom';

import '@ui5/webcomponents-icons/dist/activity-items.js';
import { WeSideBarList } from '@/utils/components/WeSideBarList';
import { WeDataKey } from '@/store/generic-data/setup';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';

const CompletedTasks: React.FC = () => {
  const { t } = useTranslation();
  const { workflowId } = useParams();

  return (
    <div className="flex ">
      <WeSideBarList
        dataKey={WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS}
        state={WorkflowState.COMPLETED}
        emptyMessage={t('tasks.empty.completed')}
      />
      <div className="absolute top-0 bottom-0 overflow-y-auto left-[280px] right-0 bottom-0 ">
        {workflowId ? (
          <Suspense>
            <Outlet />
          </Suspense>
        ) : (
          <WeEmptySection
            icon="activity-items"
            title={t('tasks.noTaskSelectedTitle')}
            text={t('tasks.noTaskSelectedText')}
          />
        )}
      </div>
    </div>
  );
};

export default CompletedTasks;
