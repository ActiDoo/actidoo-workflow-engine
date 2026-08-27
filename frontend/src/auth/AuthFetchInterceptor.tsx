// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { login } from '@/services/AuthService';
import axios from 'axios';

import { markClientOutdated } from '@/auth/clientVersion';
import { BFF_CLIENT_VERSION_HEADER, BFF_CONTRACT_VERSION } from '@/models/models';

// AuthWrapper mounts on every route, so this can run more than once. Registering
// the interceptors twice would send the header twice and handle each error twice.
let interceptorsInstalled = false;

export function interceptFetch(): void {
  if (interceptorsInstalled) return;
  interceptorsInstalled = true;

  // Set on the axios level rather than in FetchService, so the direct-axios blob
  // download in HelperService carries the header too (ADR 011).
  axios.interceptors.request.use(config => {
    config.headers.set(BFF_CLIENT_VERSION_HEADER, String(BFF_CONTRACT_VERSION));
    return config;
  });

  axios.interceptors.response.use(
    response => {
      return response;
    },
    async error => {
      // A network failure (e.g. connection reset) has no response — guard against it so
      // this handler does not throw its own TypeError and mask the real error.
      if (error.response?.status === 401) {
        login();
      }
      // 426: this bundle no longer matches the deployed backend. Not a login
      // problem — the user has to reload, so gate the app instead of redirecting.
      if (error.response?.status === 426) {
        markClientOutdated();
      }
      return await Promise.reject(error);
    }
  );
}

/** Test seam: allow a fresh install of the interceptors between tests. */
export function resetInterceptorsForTests(): void {
  interceptorsInstalled = false;
}
