// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  FetchDataResponse,
  FetchMethods,
  FetchParams,
  FetchUploadProgressFunc,
  StringDict,
} from '../models/models';
import axios from 'axios';

export async function fetchGet(url: string, params?: StringDict): Promise<FetchDataResponse> {
  return await finalFetch({
    url,
    method: FetchMethods.GET,
    params,
  });
}

export async function fetchPut(url: string, data: object): Promise<FetchDataResponse> {
  return await finalFetch({
    url,
    method: FetchMethods.PUT,
    body: JSON.stringify(data),
  });
}

export async function fetchPost(
  url: string,
  data: object,
  params?: StringDict,
  responseType?: string,
  onUploadProgress?: FetchUploadProgressFunc
): Promise<FetchDataResponse> {
  return await finalFetch({
    url,
    method: FetchMethods.POST,
    body: JSON.stringify(data),
    params,
    onUploadProgress,
  });
}

export async function fetchDel(url: string): Promise<FetchDataResponse> {
  return await finalFetch({
    url,
    method: FetchMethods.DELETE,
  });
}

export async function finalFetch(params: FetchParams): Promise<FetchDataResponse> {
  return await new Promise((resolve, reject) => {
    axios({
      url: params.url,
      method: params.method,
      data: params.body,
      params: params.params,
      headers: {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        accept: 'application/json',
      },
      responseType: params.responseType || 'json',
      withCredentials: true,
      onUploadProgress: progressEvent => {
        const { loaded, total } = progressEvent;
        const percentage = total ? Math.floor((loaded * 100) / total) : 0;
        params.onUploadProgress?.(percentage);
      },
    })
      .then(response => {
        resolve({
          response: response.status,
          data: response.data,
        });
      })
      .catch(e => {
        console.error('Fetch error', e);
        reject(e);
      });
  });
}
