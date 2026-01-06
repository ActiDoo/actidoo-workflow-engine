// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { StringDict } from '../models/models';
import _ from 'lodash';
import { useCallback } from 'react';

export function generateApiUrlWithParams(
  apiUrl: string,
  url: string,
  queryParams?: StringDict
): string {
  const search: URLSearchParams | undefined = queryParams
    ? new URLSearchParams(queryParams)
    : undefined;
  const final = search
    ? _.endsWith(url, '/')
      ? url.slice(0, -1) + '?' + search.toString()
      : url + '?' + search.toString()
    : _.endsWith(url, '/')
    ? url + '/'
    : url;
  const encoded = encodeURI(`${apiUrl}${_.endsWith(apiUrl, '/') ? '' : '/'}`) + final;
  return encoded;
}

export function isDev(): boolean {
  return import.meta.env.DEV;
}

export function groupBy<T>(
  array: T[],
  predicate: (value: T, index: number, array: T[]) => string
): object {
  return array.reduce<Record<string, T[]>>((acc, value, index, array) => {
    (acc[predicate(value, index, array)] ||= []).push(value);
    return acc;
  }, {});
}

export function getFormattedJsonFromString(value?: string): string {
  try {
    return value ? JSON.stringify(JSON.parse(value ?? ''), null, 2) : '';
  } catch (e) {
    return value ?? '';
  }
}

export const useAutoFocus = () => {
  return useCallback((inputElement: any) => {
    if (inputElement) {
      inputElement.focus();
    }
  }, []);
};

export const resolveAndDownloadBlob = (data: any, name: string): void => {
  let filename = name;
  filename = decodeURI(filename);
  const url = window.URL.createObjectURL(new Blob([data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  window.URL.revokeObjectURL(url);
  link.remove();
};
