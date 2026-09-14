// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { Suspense } from 'react';

import { PcDynamicPage } from '@/ui5-components';
import { Outlet } from 'react-router-dom';

const MyWorkflows: React.FC = () => {
  return (
    <PcDynamicPage
      id="pc-my-workflows"
      headerTitle={undefined}
      showHideHeaderButton={false}
      headerContentPinnable={false}>
      <Suspense>
        <Outlet />
      </Suspense>
    </PcDynamicPage>
  );
};

export default MyWorkflows;
