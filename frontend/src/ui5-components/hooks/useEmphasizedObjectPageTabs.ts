// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useEffect } from 'react';

import { EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE } from '@/ui5-components/styles/EmphasizedObjectPageTabs';

export const useEmphasizedObjectPageTabs = (pageId: string, updateKey?: string) => {
  useEffect(() => {
    const page = document.getElementById(pageId);
    if (!page) return;

    const observer = new MutationObserver(() => {
      const tabContainer = page.querySelector('ui5-tabcontainer');

      if (tabContainer && !tabContainer.hasAttribute(EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE)) {
        tabContainer.setAttribute(EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE, '');
        observer.disconnect();
      }
    });

    const existing = page.querySelector('ui5-tabcontainer');
    if (existing && !existing.hasAttribute(EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE)) {
      existing.setAttribute(EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE, '');
      return;
    }

    observer.observe(page, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
    };
  }, [pageId, updateKey]);
};
