// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { PropsWithChildren } from 'react';
import '@ui5/webcomponents-icons/dist/log';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/search';
import { PcPageHeader } from './pc-page-header/PcPageHeader';

export interface PcPageProps extends PropsWithChildren {
  header?: PcPageHeaderData;
  innerSpacing?: boolean;
}

export interface PcPageHeaderData {
  title: string;
  actionSection?: JSX.Element;
  showBack?: boolean;
  forceBackTo?: string;
  searchInput?: (val?: string) => void;
  initialSearch?: string;
  error?: string;
}

export const PcPage: React.FC<PcPageProps> = props => {
  const { header } = props;
  const innerSpacing = props.innerSpacing ?? true;
  return (
    <>
      {header && <PcPageHeader header={header} />}
      <div className={`flex-1 ${header && innerSpacing ? 'px-12 py-8' : 'pc-page__no-spacing'}`}>
        {props.children}
      </div>
    </>
  );
};
