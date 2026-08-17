// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';

import { PcDetailsPage, useEmphasizedObjectPageTabs } from '@/ui5-components';
import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useTranslation } from '@/i18n';

const MyWorkflows: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const selectedTab = 'all';

  useEmphasizedObjectPageTabs('pc-my-workflows', selectedTab);
  return (
    <PcDetailsPage
      id="pc-my-workflows"
      mode={ObjectPageMode.IconTabBar}
      headerTitle={undefined}
      selectedSectionId={selectedTab}
      onSelectedSectionChange={event => {
        navigate(`${event.detail.selectedSectionId}`);
      }}>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('myWorkflows.all')}
        id="all"
        titleText={t('myWorkflows.all')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default MyWorkflows;
