// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export enum FetchMethods {
  GET = 'GET',
  PUT = 'PUT',
  POST = 'POST',
  DELETE = 'DELETE',
}

export type StringDict = Record<string, any>;

export interface PcSortItem {
  id: string;
  sortDirection: string;
}
export enum TableQueryParams {
  SEARCH = 'search',
  OFFSET = 'offset',
  SORT = 'sort',
  LIMIT = 'limit',
}

export interface GetRequestAdditionalData {
  params?: StringDict;
  queryParams?: StringDict;
  keepData?: boolean;
}

export interface FetchDataResponse {
  data: any;
  response: number;
}

export type FetchUploadProgressFunc = (percentage: number) => void;
export interface FetchParams {
  url: string;
  method: FetchMethods;
  body?: BodyInit;
  params?: StringDict;
  responseType?: XMLHttpRequestResponseType;
  onUploadProgress?: FetchUploadProgressFunc;
}

export interface SimpleActionInput {
  type: string;
}

export interface ItemsAndCountResponse<T> {
  ITEMS: T[];
  COUNT: number;
}

export interface HTTPValidationError {
  detail: HTTPValidationErrorDetail[];
}
export interface HTTPValidationErrorDetail {
  loc: string[];
  msg: string;
  type: string;
}
export interface PcTableData {
  filter: StringDict;
  onFilter: any;
  sort: PcSortItem | undefined;
}
