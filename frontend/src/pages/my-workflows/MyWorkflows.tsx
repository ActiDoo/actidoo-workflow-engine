// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';

import { PcDetailsPage } from '@/ui5-components';
import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from '@/i18n';

const MyWorkflows: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const path = window.location.pathname;
  const selectedTab = path.includes('completed') ? 'completed' : 'progress';

  return (
    <PcDetailsPage
      mode={ObjectPageMode.IconTabBar}
      header={{
        title: t('myWorkflows.title'),
      }}
      selectedSectionId={selectedTab}
      onSelectedSectionChange={event => {
        navigate(`${event.detail.selectedSectionId}`);
      }}>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('myWorkflows.inProgress')}
        id="progress"
        titleText={t('myWorkflows.inProgress')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('myWorkflows.completed')}
        id="completed"
        titleText={t('myWorkflows.completed')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default MyWorkflows;
