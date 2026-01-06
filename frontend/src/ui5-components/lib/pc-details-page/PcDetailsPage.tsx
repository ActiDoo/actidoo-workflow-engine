// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useNavigate } from 'react-router-dom';
import {
  DynamicPageTitle,
  Icon,
  Link,
  MessageStrip,
  MessageStripDesign,
  ObjectPage,
  ObjectPagePropTypes,
  Title,
} from '@ui5/webcomponents-react';
import React, { ReactElement } from 'react';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';
import '@/ui5-components/lib/pc-details-page/PcDetailsPage.scss';
export interface PcDetailsPageProps extends ObjectPagePropTypes {
  header?: PcPageHeaderData;
  children?: ReactElement[] | ReactElement;
}

export const PcDetailsPage: React.FC<PcDetailsPageProps> = props => {
  const navigate = useNavigate();
  const header = (
    <DynamicPageTitle
      actions={props.header?.actionSection}
      header={
        <div className="flex items-center pt-2 w-full">
          {props.header?.showBack ? (
            <Link
              onClick={() => {
                if (props.header?.forceBackTo) navigate(props.header?.forceBackTo);
                else navigate(-1);
              }}>
              <Icon name="nav-back" className="w-8 h-full -ml-2" />
            </Link>
          ) : null}
          <Title className="flex-1">{props.header?.title}</Title>
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
    <ObjectPage style={{ maxHeight: 'calc(100vh - 44px)' }} headerTitle={header} {...props}>
      {props.children}
    </ObjectPage>
  );
};
