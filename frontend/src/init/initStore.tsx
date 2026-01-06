// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { applyMiddleware, compose, createStore } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { persistReducer, persistStore } from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import { rootReducer, rootSaga } from '@/store';
import { isDev } from '@/ui5-components';

declare global {
  interface Window {
    __REDUX_DEVTOOLS_EXTENSION_COMPOSE__: any;
  }
}

const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['none'],
};
const persistedReducer = persistReducer(persistConfig, rootReducer);

const sagaMiddleware = createSagaMiddleware();
let reduxStore = null;
if (isDev()) {
  const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
  reduxStore = createStore(
    persistedReducer,
    undefined,
    composeEnhancers(applyMiddleware(sagaMiddleware))
  );
} else {
  reduxStore = createStore(persistedReducer, undefined, applyMiddleware(sagaMiddleware));
}
const reduxPersistor = persistStore(reduxStore);

sagaMiddleware.run(rootSaga);

export const store = reduxStore;
export const persistor = reduxPersistor;
