// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { ObjectPage, ObjectPagePropTypes } from '@ui5/webcomponents-react';
import React, { ReactElement } from 'react';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';
import { PcPageTitle } from '@/ui5-components/lib/pc-page-title/PcPageTitle';
import '@/ui5-components/lib/pc-details-page/PcDetailsPage.scss';
export interface PcDetailsPageProps extends ObjectPagePropTypes {
  header?: PcPageHeaderData;
  children?: ReactElement[] | ReactElement;
}

export const PcDetailsPage: React.FC<PcDetailsPageProps> = props => {
  return (
    <ObjectPage
      style={{ maxHeight: 'calc(100vh - 44px)' }}
      headerTitle={<PcPageTitle header={props.header} />}
      {...props}>
      {props.children}
    </ObjectPage>
  );
};
