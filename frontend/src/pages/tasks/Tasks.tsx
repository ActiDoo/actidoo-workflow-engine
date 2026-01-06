// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import '@/pages/tasks/Tasks.scss';

import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { PcDetailsPage } from '@/ui5-components';
import { useTranslation } from '@/i18n';

const Tasks: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const selectedTab = window.location.pathname.includes('open') ? 'open' : 'completed';

  return (
    <PcDetailsPage
      id="pc-tasks"
      mode={ObjectPageMode.IconTabBar}
      header={{
        title: t('tasks.header'),
      }}
      className={'!p-0'}
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
