// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';

import { PcDetailsPage } from '@/ui5-components';
import { useTranslation } from '@/i18n';

const About: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const selectedTab = pathname.includes('/notices') ? 'notices' : 'help';

  return (
    <PcDetailsPage
      id="pc-about"
      mode={ObjectPageMode.IconTabBar}
      header={{ title: t('about.title') }}
      onSelectedSectionChange={event => {
        if (event.detail.selectedSectionId !== selectedTab) {
          navigate(event.detail.selectedSectionId);
        }
      }}
      selectedSectionId={selectedTab}>
      <ObjectPageSection
        className="mt-8"
        aria-label={t('about.help.tab')}
        id="help"
        titleText={t('about.help.tab')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
      <ObjectPageSection
        className="mt-8"
        aria-label={t('about.thirdPartyTitle')}
        id="notices"
        titleText={t('about.thirdPartyTitle')}>
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default About;
