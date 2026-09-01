// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import { useNavigate } from 'react-router-dom';

/**
 * Back navigation shared by the page containers (PcPageTitle, PcActionBar).
 *
 * Prefer real history navigation so query state (filters, version) of the
 * previous page is restored and the browser history stays clean; forceBackTo
 * only catches deep-link entries with no in-app history (react-router writes
 * idx into history.state).
 */
export const useBackNavigation = (forceBackTo?: string): (() => void) => {
  const navigate = useNavigate();

  return () => {
    const hasInAppHistory = (window.history.state?.idx ?? 0) > 0;
    if (hasInAppHistory || !forceBackTo) navigate(-1);
    else navigate(forceBackTo);
  };
};
