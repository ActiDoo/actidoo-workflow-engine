// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { DynamicPage, DynamicPagePropTypes } from '@ui5/webcomponents-react';
import React from 'react';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';
import { PcPageTitle } from '@/ui5-components/lib/pc-page-title/PcPageTitle';
import '@/ui5-components/lib/pc-dynamic-page/PcDynamicPage.scss';

export interface PcDynamicPageProps extends DynamicPagePropTypes {
  header?: PcPageHeaderData;
}

export const PcDynamicPage: React.FC<PcDynamicPageProps> = props => {
  return (
    <DynamicPage
      style={{ maxHeight: 'calc(100vh - 44px)' }}
      headerTitle={<PcPageTitle header={props.header} />}
      {...props}>
      {props.children}
    </DynamicPage>
  );
};
