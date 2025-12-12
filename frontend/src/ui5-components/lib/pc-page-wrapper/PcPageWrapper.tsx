import React, { PropsWithChildren, ReactElement } from 'react';
import { NavLink } from 'react-router-dom';

import { Link as RouterLink } from 'react-router-dom';

import { Bar, Icon, Button, ButtonDesign, Text } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/log';
import '@ui5/webcomponents-icons/dist/action-settings';

import { PcNavigationItem } from '@/ui5-components/lib/pc-page-wrapper/pc-navigation-item/PcNavigaionItem';

export interface PcPageWrapperProps extends PropsWithChildren {
  appTitle?: string;
  user?: string;
  navigation?: Array<PcNavigationLink | undefined>;
  endHeaderActions?: ReactElement;
  logoLink?: string;
  brandLogoUrl?: string;
  onNavigate?: () => void;
  onLogout?: () => void;
  settingsRoute? : string;
}

export interface PcNavigationLink {
  title: string;
  to?: string;
  activeRoute?: string;
  sub?: PcNavigationLink[];
}

export const PcPageWrapper: React.FC<PcPageWrapperProps> = props => {
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
        <Text>{props.appTitle}</Text>
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
        <RouterLink to={props.settingsRoute} className="mr-4">
           <Icon
            name="action-settings"
            interactive={true} // makes it hover/focusable like a button
            title="Settings"
            className="cursor-pointer align-middle text-4xl"
            style={{
              fontSize: '1.3rem',    // bump size up (24px)
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
        title="Sign out"
        design={ButtonDesign.Transparent}
        onClick={props.onLogout ? props.onLogout : undefined}
      />
    </div>
  );

  return (
    <div className="bg-pc-gray-50 h-screen overflow-hidden">
      <Bar
        startContent={startHeaderContent}
        endContent={endHeaderContent}
        className="z-[100] fixed top-0 pc-px-header-responsive "
      />
      <div className="relative flex flex-col flex-1 overflow-auto mt-11 h-[calc(100vh-2.75rem)]">
        {props.children}
      </div>
    </div>
  );
};
