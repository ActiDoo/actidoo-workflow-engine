// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import React from 'react';
import { Provider } from 'react-redux';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AuthWrapper } from '@/auth/AuthWrapper';
import { markClientOutdated, resetClientVersionStateForTests } from '@/auth/clientVersion';
import { I18nProvider } from '@/i18n';
import { en } from '@/i18n/locales/en';

// The gate has to win over auth, so the auth side effects are stubbed out and the
// login state says "logged in and authorized" - the state in which the wrapper
// would otherwise render the app.
const login = vi.hoisted(() => vi.fn());
vi.mock('@/services/AuthService', () => ({ login, logout: vi.fn() }));
vi.mock('@/auth/AuthFetchInterceptor', () => ({
  interceptFetch: vi.fn(),
  resetInterceptorsForTests: vi.fn(),
}));

// One stable object: react-redux compares snapshots by identity, so rebuilding the
// state on every getState() would re-render forever.
const state = {
  auth: { loginState: { response: 200, data: { is_logged_in: true, can_access_wf: true } } },
  data: { 'user-settings': { response: 200, data: { locale: 'en' } } },
};

const store = {
  subscribe: () => () => undefined,
  dispatch: vi.fn(),
  getState: () => state,
};

const renderWrapper = () =>
  render(
    <Provider store={store as never}>
      <I18nProvider>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route element={<AuthWrapper />}>
              <Route path="/" element={<div>the application</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </I18nProvider>
    </Provider>
  );

describe('AuthWrapper client-version gate', () => {
  beforeEach(() => {
    resetClientVersionStateForTests();
    login.mockClear();
  });

  afterEach(() => {
    resetClientVersionStateForTests();
  });

  it('renders the application while the client version matches', async () => {
    renderWrapper();

    expect(await screen.findByText('the application')).toBeTruthy();
  });

  it('replaces the whole application with the reload gate once the client is outdated', async () => {
    markClientOutdated();
    const { container } = renderWrapper();

    // A full-page gate: the app must not be reachable behind it, because every BFF
    // call would be refused anyway (ADR 011).
    expect(screen.queryByText('the application')).toBeNull();

    // The title lives on the UI5 web component's attribute, not in the light DOM.
    const message = container.querySelector('ui5-illustrated-message');
    expect(message?.getAttribute('title-text')).toBe(en.auth.clientVersionMismatchTitle);

    // A version mismatch is not an auth problem - a login redirect would loop.
    expect(login).not.toHaveBeenCalled();
  });
});
