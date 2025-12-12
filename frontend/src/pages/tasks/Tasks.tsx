import React, { Suspense } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import '@/pages/tasks/Tasks.scss';

import { ObjectPageMode, ObjectPageSection } from '@ui5/webcomponents-react';
import { PcDetailsPage } from '@/ui5-components';

const Tasks: React.FC = () => {
  const navigate = useNavigate();
  const selectedTab = window.location.pathname.includes('open') ? 'open' : 'completed';

  return (
    <PcDetailsPage
      id="pc-tasks"
      mode={ObjectPageMode.IconTabBar}
      header={{
        title: 'Tasks',
      }}
      className={'!p-0'}
      onSelectedSectionChange={event => {
        if (event.detail.selectedSectionId !== selectedTab) {
          navigate(event.detail.selectedSectionId);
        }
      }}
      selectedSectionId={selectedTab}>
      <ObjectPageSection className="!p-0" aria-label="Open" id="open" titleText="Open">
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
      <ObjectPageSection aria-label="Completed" id="completed" titleText="Completed">
        <Suspense>
          <Outlet />
        </Suspense>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};

export default Tasks;
