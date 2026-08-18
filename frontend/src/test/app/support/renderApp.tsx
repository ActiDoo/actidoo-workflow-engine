// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Renders real pages on a real store (reducers + sagas) behind a memory router, the way
// main.tsx assembles the app minus auth and shell. The HTTP layer is replaced per test
// file with a fake BFF (see fakeBff.ts and the vi.mock line in a test), so a test can
// move between pages and check that they show what the backend currently has. Pages are
// driven with Vitest's browser locators (`page` from 'vitest/browser').

import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { Provider } from 'react-redux';
import { applyMiddleware, createStore } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router-dom';
import { ThemeProvider } from '@ui5/webcomponents-react';

import { I18nProvider } from '@/i18n';
import { rootReducer, rootSaga } from '@/store';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';

export const renderApp = (routes: RouteObject[], initialPath: string) => {
  const sagaMiddleware = createSagaMiddleware();
  const store = createStore(rootReducer, applyMiddleware(sagaMiddleware));
  sagaMiddleware.run(rootSaga);
  // AuthWrapper loads the current user once after login; pages read it from the store.
  store.dispatch(postRequest(WeDataKey.WFE_USER, {}));

  const router = createMemoryRouter(routes, { initialEntries: [initialPath] });

  render(
    <I18nProvider>
      <Provider store={store}>
        <ThemeProvider>
          <RouterProvider router={router} />
        </ThemeProvider>
      </Provider>
    </I18nProvider>
  );

  const navigate = async (to: string): Promise<void> => {
    await router.navigate(to);
  };

  return { store, router, navigate };
};

export const route = (path: string, element: ReactElement): RouteObject => ({ path, element });
