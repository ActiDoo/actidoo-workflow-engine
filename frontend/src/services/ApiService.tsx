// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { environment } from '@/environment';
import { generateApiUrlWithParams, StringDict } from '@/ui5-components';

const adminRequest = ['all_tasks'];

export function getApiUrl(url: string, queryParams?: StringDict): string {
  const apiUrl = adminRequest.includes(url) ? environment.apiUrlAdmin : environment.apiUrl;
  return generateApiUrlWithParams(apiUrl, url, queryParams);
}

export function getAuthApiUrl(url: string, queryParams?: StringDict): string {
  return generateApiUrlWithParams(environment.authApiUrl, url, queryParams);
}
