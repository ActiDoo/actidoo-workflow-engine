// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useNavigate } from 'react-router-dom';
import {
  DynamicPageTitle,
  Icon,
  Link,
  MessageStrip,
  MessageStripDesign,
  Title,
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
 * drifts from the app-wide 32px "72-Bold" page-title typography. The ref is
 * forwarded because the page containers attach one to their headerTitle.
 *
 * The top padding is owned here so every page container shows the title at the
 * same offset: 19px plus the 5px the title slot adds internally equals the 24px
 * (`py-6`) gap of PcPage's header.
 */
export const PcPageTitle = React.forwardRef<HTMLDivElement, PcPageTitleProps>((props, ref) => {
  const navigate = useNavigate();
  // DynamicPage/ObjectPage clone their headerTitle element and inject props into
  // it (data-not-clickable, the header-toggle handler, ...). They must reach the
  // inner DynamicPageTitle, otherwise the title shows a hover/pointer although
  // there is no header content to toggle.
  const { header, ...injected } = props;
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
                // Prefer real history navigation so query state (filters, version)
                // of the previous page is restored and the browser history stays
                // clean; forceBackTo only catches deep-link entries with no
                // in-app history (react-router writes idx into history.state).
                const hasInAppHistory = (window.history.state?.idx ?? 0) > 0;
                if (hasInAppHistory || !header?.forceBackTo) navigate(-1);
                else navigate(header.forceBackTo);
              }}>
              <Icon name="nav-back" className="w-8 h-full -ml-2" />
            </Link>
          ) : null}
          <Title className="flex-1">{header?.title}</Title>
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
