// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Icon, LinkDomRef, Menu, MenuDomRef, MenuItem, Text } from '@ui5/webcomponents-react';
import { NavLink, useNavigate } from 'react-router-dom';
import React, { MutableRefObject, useRef } from 'react';
import '@ui5/webcomponents-icons/dist/navigation-down-arrow';
import { PcNavigationLink } from '@/ui5-components/lib/pc-page-wrapper/PcPageWrapper';

interface PcNavigationItemProps {
  item: PcNavigationLink;
  onNavigate?: () => void;
}

export const PcNavigationItem: React.FC<PcNavigationItemProps> = (props: PcNavigationItemProps) => {
  const { item } = props;
  const navigate = useNavigate();

  const menuRef: MutableRefObject<MenuDomRef> | undefined = useRef() as
    | MutableRefObject<MenuDomRef>
    | undefined;
  const buttonRef: MutableRefObject<LinkDomRef> | undefined = useRef() as
    | MutableRefObject<LinkDomRef>
    | undefined;

  const linkClass = (isActive: boolean): string =>
    `mr-4 h-11 !inline-flex items-center no-underline cursor-pointer ${
      isActive ? 'shadow-[inset_0px_-4px_0px_var(--pc-color-blue-primary)]' : 'link'
    }`;

  const isRouteActive = (activeRoute?: string): boolean =>
    activeRoute ? window.location.pathname?.includes(activeRoute) : false;

  const handleMenuCLick = (text: string): void => {
    const to = item.sub?.find(s => s.title === text)?.to;
    if (props.onNavigate) props.onNavigate();
    if (to) navigate(to);
  };

  const DefaultLink = (
    <NavLink
      className={({ isActive }) =>
        item.activeRoute ? linkClass(isRouteActive(item.activeRoute)) : linkClass(isActive)
      }
      to={item.to ?? ''}
      onClick={props.onNavigate}>
      <Text>{item.title}</Text>
    </NavLink>
  );

  const LinkWithSub = (
    <>
      <Text
        ref={buttonRef}
        className={linkClass(isRouteActive(item.activeRoute))}
        onClick={() => {
          menuRef?.current.showAt(buttonRef?.current as HTMLElement);
        }}>
        {item.title}
        <Icon name="navigation-down-arrow" />
      </Text>
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
