// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Icon, Menu, MenuDomRef, MenuItem } from '@ui5/webcomponents-react';
import { matchPath, NavLink, useLocation, useNavigate } from 'react-router-dom';
import React, { useRef } from 'react';
import '@ui5/webcomponents-icons/dist/navigation-down-arrow';
import { PcNavigationLink } from '@/ui5-components/lib/pc-page-wrapper/PcPageWrapper';

interface PcNavigationItemProps {
  item: PcNavigationLink;
  onNavigate?: () => void;
}

export const PcNavigationItem: React.FC<PcNavigationItemProps> = (props: PcNavigationItemProps) => {
  const { item } = props;
  const navigate = useNavigate();
  const location = useLocation();

  const menuRef = useRef<MenuDomRef>(null);
  const buttonRef = useRef<HTMLSpanElement>(null);

  const linkClass = (isActive: boolean): string =>
    `mr-4 h-11 !inline-flex items-center no-underline cursor-pointer border-b-4 ${
      isActive
        ? 'border-brand-primary text-brand-primary font-semibold'
        : 'border-transparent text-neutral-700 hover:text-neutral-900'
    }`;

  const normalizePath = (path?: string): string | undefined =>
    path ? (path.startsWith('/') ? path : `/${path}`) : undefined;

  const isRouteActive = (path?: string): boolean => {
    const normalizedPath = normalizePath(path);
    return normalizedPath
      ? matchPath({ path: normalizedPath, end: false }, location.pathname) !== null
      : false;
  };

  const handleMenuCLick = (text: string): void => {
    const to = item.sub?.find(s => s.title === text)?.to;
    if (props.onNavigate) props.onNavigate();
    if (to) navigate(to);
  };

  const isActive = isRouteActive(item.activeRoute ?? item.to);

  const DefaultLink = (
    <NavLink
      aria-current={isActive ? 'page' : undefined}
      className={linkClass(isActive)}
      to={item.to ?? ''}
      onClick={props.onNavigate}>
      <span>{item.title}</span>
    </NavLink>
  );

  const LinkWithSub = (
    <>
      <span
        ref={buttonRef}
        className={linkClass(isActive)}
        onClick={() => {
          if (buttonRef.current) menuRef.current?.showAt(buttonRef.current);
        }}
        onKeyDown={event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            if (buttonRef.current) menuRef.current?.showAt(buttonRef.current);
          }
        }}
        role="button"
        tabIndex={0}>
        {item.title}
        <Icon name="navigation-down-arrow" />
      </span>
      <Menu
        ref={menuRef}
        onItemClick={e => {
          handleMenuCLick(e.detail.text);
        }}>
        {item.sub?.map(subItem => (
          <MenuItem key={subItem.to} text={subItem.title} itemID={subItem.to} />
        ))}
      </Menu>
    </>
  );

  return item.sub ? LinkWithSub : DefaultLink;
};
