// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { PropsWithChildren, ReactElement } from 'react';
import { NavLink, Link as RouterLink } from 'react-router-dom';

import { Bar, Icon, Button, ButtonDesign, Text } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/log';
import '@ui5/webcomponents-icons/dist/action-settings';
import '@ui5/webcomponents-icons/dist/question-mark';

import { PcNavigationItem } from '@/ui5-components/lib/pc-page-wrapper/pc-navigation-item/PcNavigaionItem';
import { useTranslation } from '@/i18n';

export interface PcPageWrapperProps extends PropsWithChildren {
  appTitle?: string;
  user?: string;
  navigation?: Array<PcNavigationLink | undefined>;
  endHeaderActions?: ReactElement;
  logoLink?: string;
  brandLogoUrl?: string;
  onNavigate?: () => void;
  onLogout?: () => void;
  settingsRoute?: string;
  helpRoute?: string;
}

export interface PcNavigationLink {
  title: string;
  to?: string;
  activeRoute?: string;
  sub?: PcNavigationLink[];
}

export const PcPageWrapper: React.FC<PcPageWrapperProps> = props => {
  const { t } = useTranslation();
  const logoSrc = props.brandLogoUrl ?? '';
  const handleLogoError = (event: React.SyntheticEvent<HTMLImageElement>) => {
    event.currentTarget.onerror = null;
    event.currentTarget.src = '';
  };
  const startHeaderContent = (
    <div className="flex">
      <NavLink
        to={props.logoLink ?? '/'}
        className="flex no-underline items-center"
        onClick={props.onNavigate}>
        <img src={logoSrc} className="h-9 my-1 w-auto" onError={handleLogoError} />
        {props.appTitle ? (
          <Text className="ml-3 self-center !text-sm !text-pc-gray-700 whitespace-nowrap">
            {props.appTitle}
          </Text>
        ) : null}
      </NavLink>
      {props.navigation ? (
        <div className="mx-8 border-r border-pc-gray-200 border-r-solid h-11" />
      ) : null}
      {props.navigation?.map((item, index) =>
        item ? (
          <PcNavigationItem
            key={`PcNavigationItem${index}`}
            item={item}
            onNavigate={props.onNavigate}
          />
        ) : null
      )}
    </div>
  );

  const endHeaderContent = (
    <div className="flex items-center">
      {props.endHeaderActions}
      <div className="mx-4 border-r border-pc-gray-200 border-r-solid h-11" />

      {props.settingsRoute && (
        <RouterLink to={props.settingsRoute} className="mr-2">
          <Icon
            name="action-settings"
            interactive={true} // makes it hover/focusable like a button
            title={t('layout.settings')}
            className="cursor-pointer align-middle text-4xl"
            style={{
              fontSize: '1.3rem', // bump size up (24px)
              width: '1.3rem',
              height: '1.3rem',
              cursor: 'pointer',
            }}
          />
        </RouterLink>
      )}

      {props.helpRoute && (
        <RouterLink to={props.helpRoute} className="mr-4">
          <Icon
            name="question-mark"
            interactive={true}
            title={t('layout.about')}
            className="cursor-pointer align-middle text-4xl"
            style={{
              fontSize: '1.3rem',
              width: '1.3rem',
              height: '1.3rem',
              cursor: 'pointer',
            }}
          />
        </RouterLink>
      )}

      {props.user ? <Text className="mr-2">{props.user}</Text> : null}
      <Button
        icon="log"
        title={t('layout.signOut')}
        design={ButtonDesign.Transparent}
        onClick={props.onLogout ? props.onLogout : undefined}
      />
    </div>
  );

  // Mobile workaround until real responsiveness lands: below `md` the app keeps a
  // minimum width of 1024px and the whole shell (header included) scrolls
  // horizontally. The header is in normal flow inside the min-width column so it
  // pans along instead of being pinned to the viewport.
  return (
    <div className="bg-pc-gray-50 h-screen overflow-x-auto overflow-y-hidden">
      <div className="flex flex-col h-full max-md:min-w-[1024px]">
        <Bar
          startContent={startHeaderContent}
          endContent={endHeaderContent}
          className="z-[100] relative shrink-0 pc-px-header-responsive "
        />
        <div className="relative flex flex-col flex-1 overflow-auto">
          <div className="flex flex-col flex-1">{props.children}</div>
        </div>
      </div>
    </div>
  );
};
