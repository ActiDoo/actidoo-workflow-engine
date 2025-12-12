import React, { Suspense } from 'react';

import { PcDetailsPage } from '@/ui5-components';
import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { Outlet, useNavigate } from 'react-router-dom';

const MyWorkflows: React.FC = () => {
  const navigate = useNavigate();
  const path = window.location.pathname;
  const selectedTab = path.includes('completed') ? 'completed' : 'progress';

  return (
    <PcDetailsPage
      mode={ObjectPageMode.IconTabBar}
      header={{
        title: 'My Workflows',
      }}
      selectedSectionId={selectedTab}
      onSelectedSectionChange={event => {
        navigate(`${event.detail.selectedSectionId}`);
      }}>
      <ObjectPageSection
        className=" mt-8"
        aria-label="In progress"
        id="progress"
        titleText="In progress">
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
      <ObjectPageSection
        className=" mt-8"
        aria-label="Completed"
        id="completed"
        titleText="Completed">
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default MyWorkflows;
