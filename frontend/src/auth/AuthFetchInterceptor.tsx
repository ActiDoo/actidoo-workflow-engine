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
      if (error.response.status === 401) {
        login();
      }
      return await Promise.reject(error);
    }
  );
}
