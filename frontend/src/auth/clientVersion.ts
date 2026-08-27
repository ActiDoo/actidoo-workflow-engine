// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import axios from 'axios';

import { environment } from '@/environment';
import { BFF_CONTRACT_VERSION } from '@/models/models';

/**
 * Tracks whether this bundle still matches the deployed backend (ADR 011).
 *
 * Two things arm the flag: a 426 from any BFF call (reactive, see
 * AuthFetchInterceptor) and the poll below (proactive, so a user is told before
 * investing more work into a form that can no longer be submitted).
 *
 * The flag is deliberately one-way. During a rolling deploy a poll can hit old
 * and new pods in turn; a gate that opens again would be worse than one that
 * sends the user to reload once.
 */
let outdated = false;
const listeners = new Set<() => void>();

export const markClientOutdated = (): void => {
  if (outdated) return;
  outdated = true;
  listeners.forEach(listener => {
    listener();
  });
};

export const isClientOutdated = (): boolean => outdated;

export const subscribeClientOutdated = (listener: () => void): (() => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

// Short on purpose: the poll exists to notice early, and in the tab the user is
// actually working in every second earlier is work they do not throw away. The
// load stays at roughly one request per user because hidden tabs pause.
const POLL_INTERVAL_MS = 10_000;

/**
 * Ask the backend which BFF contract it serves and arm the gate on a mismatch.
 *
 * A failed request is ignored on purpose: only a successful answer with a
 * different version proves a mismatch. A brief backend outage or a flaky network
 * must never lock anybody out.
 */
const checkClientVersion = async (): Promise<void> => {
  try {
    // The version endpoint is unauthenticated and ungated, so this can never
    // produce a 426 itself and cannot recurse through the interceptor.
    const response = await axios.get(environment.versionUrl, {
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (response.status !== 200) return;

    const serverVersion = response.data?.bff_contract_version;
    if (typeof serverVersion === 'number' && serverVersion !== BFF_CONTRACT_VERSION) {
      markClientOutdated();
    }
  } catch {
    // Unreachable backend tells us nothing about the contract - ignore.
  }
};

let stopPolling: (() => void) | undefined;

/**
 * Start the version poll. Idempotent, so mounting AuthWrapper more than once
 * cannot stack up timers.
 *
 * Polling pauses while the tab is hidden and checks once immediately when it
 * becomes visible again. That keeps the load at one request per user rather than
 * per open tab, and it covers the multi-tab case the gate was built for: a tab
 * that sat in the background for hours is checked the moment somebody returns to
 * it, instead of waiting for the next tick.
 */
export const startClientVersionPolling = (): void => {
  if (stopPolling !== undefined) return;

  let timer: ReturnType<typeof setInterval> | undefined;

  const stop = (): void => {
    if (timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    }
  };

  const start = (): void => {
    if (timer !== undefined) return;
    timer = setInterval(() => {
      void checkClientVersion();
    }, POLL_INTERVAL_MS);
  };

  const onVisibilityChange = (): void => {
    if (document.visibilityState === 'visible') {
      void checkClientVersion();
      start();
    } else {
      stop();
    }
  };

  document.addEventListener('visibilitychange', onVisibilityChange);
  stopPolling = () => {
    document.removeEventListener('visibilitychange', onVisibilityChange);
    stop();
  };

  if (document.visibilityState === 'visible') {
    void checkClientVersion();
    start();
  }
};

/** Test seam: reset the module state between tests. */
export const resetClientVersionStateForTests = (): void => {
  outdated = false;
  listeners.clear();
  stopPolling?.();
  stopPolling = undefined;
};
