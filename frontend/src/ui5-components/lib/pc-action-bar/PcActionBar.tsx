// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import React from 'react';
import { Icon, Link, Title, TitleLevel } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/nav-back';
import { useBackNavigation } from '@/ui5-components/hooks/useBackNavigation';

export interface PcActionBarProps {
  showBack?: boolean;
  forceBackTo?: string;
  title?: string;
  actions?: JSX.Element;
}

/**
 * Back link and page actions without a page title, for pages that carry no
 * heading (only help, settings and admin pages show one).
 */
export const PcActionBar: React.FC<PcActionBarProps> = props => {
  const navigateBack = useBackNavigation(props.forceBackTo);

  if (!props.showBack && !props.actions && !props.title) return null;

  return (
    <div className="flex items-center gap-2 mb-4">
      {props.showBack ? (
        <Link
          onClick={() => {
            navigateBack();
          }}>
          <Icon name="nav-back" className="w-8 h-full -ml-2" />
        </Link>
      ) : null}
      {props.title ? (
        <Title level={TitleLevel.H5} className="min-w-0 truncate">
          {props.title}
        </Title>
      ) : null}
      <div className="flex-1"></div>
      {props.actions}
    </div>
  );
};
