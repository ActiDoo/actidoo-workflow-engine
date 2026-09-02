// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useBackNavigation } from '@/ui5-components/hooks/useBackNavigation';
import {
  DynamicPageTitle,
  Icon,
  Link,
  MessageStrip,
  MessageStripDesign,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import React from 'react';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';

export interface PcPageTitleProps {
  header?: PcPageHeaderData;
}

/**
 * Shared DynamicPageTitle for the DynamicPage/ObjectPage wrappers (PcDynamicPage,
 * PcDetailsPage). The title must render through `<Title>` — raw text in the
 * DynamicPageTitle header slot falls back to the extra-bold "72Black" cut and
 * drifts from the page-title typography. Level H3 (24px in Horizon) is the top
 * step of the app's type scale. The ref is forwarded because the page containers
 * attach one to their headerTitle.
 *
 * The top padding is owned here so every page container shows the title at the
 * same offset: 19px plus the 5px the title slot adds internally equals the 24px
 * (`py-6`) gap of PcPage's header.
 */
export const PcPageTitle = React.forwardRef<HTMLDivElement, PcPageTitleProps>((props, ref) => {
  // DynamicPage/ObjectPage clone their headerTitle element and inject props into
  // it (data-not-clickable, the header-toggle handler, ...). They must reach the
  // inner DynamicPageTitle, otherwise the title shows a hover/pointer although
  // there is no header content to toggle.
  const { header, ...injected } = props;
  const navigateBack = useBackNavigation(header?.forceBackTo);
  return (
    <DynamicPageTitle
      {...injected}
      ref={ref}
      style={{ paddingBlockStart: '19px' }}
      actions={header?.actionSection}
      header={
        <div className="flex items-center w-full">
          {header?.showBack ? (
            <Link
              onClick={() => {
                navigateBack();
              }}>
              <Icon name="nav-back" className="w-8 h-full -ml-2" />
            </Link>
          ) : null}
          <Title level={TitleLevel.H3} className="flex-1">
            {header?.title}
          </Title>
        </div>
      }
      showSubHeaderRight={false}
      subHeader={
        header?.error ? (
          <MessageStrip design={MessageStripDesign.Negative} hideCloseButton={true}>
            {header?.error}
          </MessageStrip>
        ) : undefined
      }></DynamicPageTitle>
  );
});

PcPageTitle.displayName = 'PcPageTitle';
