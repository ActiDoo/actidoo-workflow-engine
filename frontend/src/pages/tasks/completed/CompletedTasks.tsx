// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';
import { Outlet, useNavigate, useParams } from 'react-router-dom';

import '@ui5/webcomponents-icons/dist/activity-items.js';
import '@ui5/webcomponents-icons/dist/nav-back.js';
import { Button, ButtonDesign } from '@ui5/webcomponents-react';
import { WeSideBarList } from '@/utils/components/WeSideBarList';
import { WeDataKey } from '@/store/generic-data/setup';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { WorkflowState } from '@/models/models';
import { useTranslation } from '@/i18n';

const CompletedTasks: React.FC = () => {
  const { t } = useTranslation();
  const { workflowId } = useParams();
  const navigate = useNavigate();

  // Below `md` the list and detail are separate pages (drill-down): the list is
  // shown until a task is picked, then the detail takes over. From `md` up both
  // are visible side by side as a master-detail layout.
  return (
    <div className="flex ">
      <WeSideBarList
        dataKey={WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS}
        state={WorkflowState.COMPLETED}
        emptyMessage={t('tasks.empty.completed')}
        className={`w-full md:w-[280px] ${workflowId ? 'hidden md:block' : ''}`}
      />
      <div
        className={`absolute top-0 bottom-0 right-0 overflow-auto left-0 md:left-[280px] ${
          workflowId ? '' : 'hidden md:block'
        }`}>
        {workflowId ? (
          <>
            <div className="md:hidden sticky top-0 z-10 bg-white pl-[7px] pt-1 pb-2">
              {/* borderless so the chevron — not a button box — lines up with the
                  content's 16px left edge */}
              <Button
                design={ButtonDesign.Transparent}
                icon="nav-back"
                style={{ border: 'none' }}
                onClick={() => {
                  navigate('/tasks/completed');
                }}>
                {t('tasks.backToList')}
              </Button>
            </div>
            <Suspense>
              <Outlet />
            </Suspense>
          </>
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
