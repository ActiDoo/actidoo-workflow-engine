// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { interceptFetch, resetInterceptorsForTests } from '@/auth/AuthFetchInterceptor';
import { isClientOutdated, resetClientVersionStateForTests } from '@/auth/clientVersion';
import { BFF_CLIENT_VERSION_HEADER, BFF_CONTRACT_VERSION } from '@/models/models';

const login = vi.hoisted(() => vi.fn());
vi.mock('@/services/AuthService', () => ({ login }));

/** Run a request through the registered request interceptors. */
const runRequestInterceptors = async (): Promise<Record<string, unknown>> => {
  const manager = axios.interceptors.request as unknown as {
    handlers: Array<{ fulfilled: (c: unknown) => unknown } | null>;
  };
  let config: unknown = { headers: new axios.AxiosHeaders() };
  for (const handler of manager.handlers) {
    if (handler?.fulfilled) config = await handler.fulfilled(config);
  }
  return (config as { headers: Record<string, unknown> }).headers;
};

/** Push an error through the registered response interceptors. */
const runResponseErrorInterceptors = async (status: number): Promise<void> => {
  const manager = axios.interceptors.response as unknown as {
    handlers: Array<{ rejected: (e: unknown) => Promise<unknown> } | null>;
  };
  for (const handler of manager.handlers) {
    if (handler?.rejected) {
      await handler.rejected({ response: { status } }).catch(() => undefined);
    }
  }
};

describe('interceptFetch', () => {
  beforeEach(() => {
    axios.interceptors.request.clear();
    axios.interceptors.response.clear();
    resetInterceptorsForTests();
    resetClientVersionStateForTests();
    login.mockClear();
  });

  afterEach(() => {
    axios.interceptors.request.clear();
    axios.interceptors.response.clear();
  });

  it('sends the BFF contract version on every request', async () => {
    interceptFetch();

    const headers = await runRequestInterceptors();

    expect(headers[BFF_CLIENT_VERSION_HEADER]).toBe(String(BFF_CONTRACT_VERSION));
  });

  it('starts a login on 401', async () => {
    interceptFetch();

    await runResponseErrorInterceptors(401);

    expect(login).toHaveBeenCalledTimes(1);
    expect(isClientOutdated()).toBe(false);
  });

  it('arms the client-version gate on 426 instead of logging in', async () => {
    interceptFetch();

    await runResponseErrorInterceptors(426);

    expect(isClientOutdated()).toBe(true);
    // A version mismatch is not an auth problem; redirecting to login would loop.
    expect(login).not.toHaveBeenCalled();
  });

  it('leaves other errors alone', async () => {
    interceptFetch();

    await runResponseErrorInterceptors(500);

    expect(login).not.toHaveBeenCalled();
    expect(isClientOutdated()).toBe(false);
  });

  it('survives a network failure that has no response', async () => {
    interceptFetch();
    const manager = axios.interceptors.response as unknown as {
      handlers: Array<{ rejected: (e: unknown) => Promise<unknown> } | null>;
    };

    for (const handler of manager.handlers) {
      if (handler?.rejected) {
        await expect(handler.rejected(new Error('connection reset'))).rejects.toThrow(
          'connection reset'
        );
      }
    }

    expect(login).not.toHaveBeenCalled();
  });

  it('installs the interceptors only once, however often AuthWrapper mounts', async () => {
    interceptFetch();
    interceptFetch();
    interceptFetch();

    await runResponseErrorInterceptors(401);

    // Registering twice would send the header twice and handle each error twice.
    expect(login).toHaveBeenCalledTimes(1);
  });
});
