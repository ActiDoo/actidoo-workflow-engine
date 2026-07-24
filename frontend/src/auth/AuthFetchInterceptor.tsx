// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { login } from '@/services/AuthService';
import axios from 'axios';

export function interceptFetch(): void {
  // const { fetch: originalFetch } = window;

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
      return await Promise.reject(error);
    }
  );
}
