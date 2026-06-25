// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useEffect } from 'react';

import { EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE } from '@/ui5-components/styles/EmphasizedObjectPageTabs';

export const useEmphasizedObjectPageTabs = (pageId: string, updateKey?: string) => {
  useEffect(() => {
    const page = document.getElementById(pageId);

    const markTabContainer = () => {
      page
        ?.querySelector('ui5-tabcontainer')
        ?.setAttribute(EMPHASIZED_OBJECT_PAGE_TABS_ATTRIBUTE, '');
    };

    markTabContainer();
    const animationFrameId = window.requestAnimationFrame(markTabContainer);
    const observer = new MutationObserver(markTabContainer);

    if (page) {
      observer.observe(page, { childList: true, subtree: true });
    }

    return () => {
      window.cancelAnimationFrame(animationFrameId);
      observer.disconnect();
    };
  }, [pageId, updateKey]);
};
