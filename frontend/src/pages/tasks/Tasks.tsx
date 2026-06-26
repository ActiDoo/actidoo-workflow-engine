// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import '@/pages/tasks/Tasks.scss';
import '@/pages/tasks/TasksTabStyles';

import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { PcDetailsPage } from '@/ui5-components';
import { useTranslation } from '@/i18n';

const Tasks: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const selectedTab = pathname.includes('/completed') ? 'completed' : 'open';
  // A task is open when the route carries a segment beyond /tasks/open|completed.
  // Used to hide the page header + tab bar on mobile (see Tasks.scss).
  const isDetail = /\/tasks\/(open|completed)\/.+/.test(pathname);

  useEffect(() => {
    const tasksPage = document.getElementById('pc-tasks');

    const markTasksTabContainer = () => {
      tasksPage?.querySelector('ui5-tabcontainer')?.setAttribute('data-tasks-tab-container', '');
    };

    markTasksTabContainer();
    const animationFrameId = window.requestAnimationFrame(markTasksTabContainer);
    const observer = new MutationObserver(markTasksTabContainer);

    if (tasksPage) {
      observer.observe(tasksPage, { childList: true, subtree: true });
    }

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      observer.disconnect();
    };
  }, [selectedTab]);

  return (
    <PcDetailsPage
      id="pc-tasks"
      mode={ObjectPageMode.IconTabBar}
      headerTitle={undefined}
      className={`!p-0 ${isDetail ? 'pc-tasks--detail' : ''}`}
      onSelectedSectionChange={event => {
        if (event.detail.selectedSectionId !== selectedTab) {
          navigate(event.detail.selectedSectionId);
        }
      }}
      selectedSectionId={selectedTab}>
      <ObjectPageSection
        className="!p-0"
        aria-label={t('tasks.tabs.open')}
        id="open"
        titleText={t('tasks.tabs.open')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
      <ObjectPageSection
        aria-label={t('tasks.tabs.completed')}
        id="completed"
        titleText={t('tasks.tabs.completed')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default Tasks;
