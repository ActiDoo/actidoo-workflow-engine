// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  isClientOutdated,
  markClientOutdated,
  resetClientVersionStateForTests,
  startClientVersionPolling,
  subscribeClientOutdated,
} from '@/auth/clientVersion';
import { BFF_CONTRACT_VERSION } from '@/models/models';

const okResponse = (version: number) => ({ status: 200, data: { bff_contract_version: version } });

/** jsdom reports 'visible' and has no setter, so the property is stubbed. */
const setVisibility = (state: DocumentVisibilityState): void => {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true });
  document.dispatchEvent(new Event('visibilitychange'));
};

describe('clientVersion', () => {
  beforeEach(() => {
    resetClientVersionStateForTests();
    setVisibility('visible');
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('notifies subscribers when the client is marked outdated', () => {
    const listener = vi.fn();
    subscribeClientOutdated(listener);

    markClientOutdated();

    expect(isClientOutdated()).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('stays outdated once armed, so a rolling deploy cannot reopen the gate', () => {
    const listener = vi.fn();
    subscribeClientOutdated(listener);

    markClientOutdated();
    markClientOutdated();

    expect(isClientOutdated()).toBe(true);
    // Only the transition notifies; repeated arming must not re-render the app.
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('arms the gate when the backend reports a different contract version', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue(okResponse(BFF_CONTRACT_VERSION + 1));

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(0);

    expect(isClientOutdated()).toBe(true);
  });

  it('leaves the gate closed while the versions match', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue(okResponse(BFF_CONTRACT_VERSION));

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(30_000);

    expect(isClientOutdated()).toBe(false);
  });

  it('ignores an unreachable backend', async () => {
    vi.spyOn(axios, 'get').mockRejectedValue(new Error('network down'));

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(30_000);

    // A failed request says nothing about the contract - locking users out over a
    // brief outage would be worse than checking again later.
    expect(isClientOutdated()).toBe(false);
  });

  it('ignores a non-200 answer', async () => {
    vi.spyOn(axios, 'get').mockResolvedValue({ status: 503, data: {} });

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(30_000);

    expect(isClientOutdated()).toBe(false);
  });

  it('polls repeatedly while the tab is visible', async () => {
    const get = vi.spyOn(axios, 'get').mockResolvedValue(okResponse(BFF_CONTRACT_VERSION));

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(0);
    const afterStart = get.mock.calls.length;

    await vi.advanceTimersByTimeAsync(30_000);

    expect(get.mock.calls.length).toBeGreaterThan(afterStart);
  });

  it('pauses while the tab is hidden and checks immediately when it returns', async () => {
    const get = vi.spyOn(axios, 'get').mockResolvedValue(okResponse(BFF_CONTRACT_VERSION));

    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(0);

    setVisibility('hidden');
    const whenHidden = get.mock.calls.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(get.mock.calls.length).toBe(whenHidden);

    // Returning to the tab must not wait for the next tick - this is the multi-tab
    // case the gate was built for.
    setVisibility('visible');
    await vi.advanceTimersByTimeAsync(0);
    expect(get.mock.calls.length).toBe(whenHidden + 1);
  });

  it('starts only once, so remounting cannot stack up timers', async () => {
    const get = vi.spyOn(axios, 'get').mockResolvedValue(okResponse(BFF_CONTRACT_VERSION));

    startClientVersionPolling();
    startClientVersionPolling();
    await vi.advanceTimersByTimeAsync(0);

    expect(get).toHaveBeenCalledTimes(1);
  });
});
