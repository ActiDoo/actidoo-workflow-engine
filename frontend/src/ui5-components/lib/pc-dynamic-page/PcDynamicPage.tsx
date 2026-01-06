// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useNavigate } from 'react-router-dom';
import {
  DynamicPage,
  DynamicPagePropTypes,
  DynamicPageTitle,
  Icon,
  Link,
  MessageStrip,
  MessageStripDesign,
} from '@ui5/webcomponents-react';
import React, { ReactElement } from 'react';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';
import '@/ui5-components/lib/pc-dynamic-page/PcDynamicPage.scss';

export interface PcDynamicPageProps extends DynamicPagePropTypes {
  header?: PcPageHeaderData;
  children?: ReactElement[] | ReactElement;
}

export const PcDynamicPage: React.FC<PcDynamicPageProps> = props => {
  const navigate = useNavigate();
  const header = (
    <DynamicPageTitle
      actions={props.header?.actionSection}
      className="!pt-6"
      header={
        <div className="flex items-center w-full">
          {props.header?.showBack ? (
            <Link
              onClick={() => {
                if (props.header?.forceBackTo) navigate(props.header?.forceBackTo);
                else navigate(-1);
              }}>
              <Icon name="nav-back" className="w-8 h-full -ml-2" />
            </Link>
          ) : null}
          {props.header?.title}
        </div>
      }
      showSubHeaderRight={false}
      subHeader={
        props.header?.error ? (
          <MessageStrip design={MessageStripDesign.Negative} hideCloseButton={true}>
            {props.header?.error}
          </MessageStrip>
        ) : undefined
      }></DynamicPageTitle>
  );
  return (
    <DynamicPage style={{ maxHeight: 'calc(100vh - 44px)' }} headerTitle={header} {...props}>
      {props.children}
    </DynamicPage>
  );
};
