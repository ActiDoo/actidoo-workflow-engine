// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Replacement for '@/ui5-components/services/FetchService' in browser tests: every request
// the app makes ends up in one handler that the test registers. Wire it in with a single
// (hoisted) line at the top of the test file:
//
//   vi.mock('@/ui5-components/services/FetchService', async () =>
//     (await import('@/test/support/fakeFetchService')).mockedFetchService()
//   );
//
// and register a handler with useFakeBackend(...) before rendering. A request without a
// handler, or one the handler throws on, fails the test with the request in the message.

import type { FetchDataResponse, FetchParams, StringDict } from '@/ui5-components/models/models';

export interface FakeFetchCall {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  body?: unknown;
  queryParams?: StringDict;
}

export interface FakeFetchResult {
  data: unknown;
  response?: number;
}
export type FakeFetchHandler = (call: FakeFetchCall) => FakeFetchResult | Promise<FakeFetchResult>;

let handler: FakeFetchHandler | undefined;

export const useFakeBackend = (next: FakeFetchHandler): void => {
  handler = next;
};

const dispatch = async (call: FakeFetchCall): Promise<FetchDataResponse> => {
  if (!handler) {
    throw new Error(
      `fake backend: no handler registered (useFakeBackend) for ${call.method} ${call.url}`
    );
  }
  const result = await handler(call);
  return { response: 200, ...result };
};

const parseBody = (body: BodyInit | undefined): unknown =>
  typeof body === 'string' ? JSON.parse(body) : body;

/** The full module shape of FetchService, so no original needs to be imported. */
export const mockedFetchService = (): typeof import('@/ui5-components/services/FetchService') => ({
  fetchGet: vi.fn(
    async (url: string, params?: StringDict) =>
      await dispatch({ method: 'GET', url, queryParams: params })
  ),
  fetchPost: vi.fn(
    async (url: string, data: object, params?: StringDict) =>
      await dispatch({ method: 'POST', url, body: data, queryParams: params })
  ),
  fetchPut: vi.fn(
    async (url: string, data: object) => await dispatch({ method: 'PUT', url, body: data })
  ),
  fetchDel: vi.fn(async (url: string) => await dispatch({ method: 'DELETE', url })),
  finalFetch: vi.fn(
    async (params: FetchParams) =>
      await dispatch({
        method: params.method,
        url: params.url,
        body: parseBody(params.body),
        queryParams: params.params,
      })
  ),
});
