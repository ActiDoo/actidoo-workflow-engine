// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { all, call, delay, put, takeEvery } from 'redux-saga/effects';
import * as UiActions from '@/store/ui/actions';
import * as GenericDataActions from '@/store/generic-data/actions';

import { getApiUrl } from '@/services/ApiService';
import {
  fetchDel,
  fetchGet,
  FetchMethods,
  fetchPost,
  fetchPut,
  GenericDataActionType,
  GenericDeleteRequestAction,
  GenericGetRequestAction,
  GenericPostRequestAction,
  GenericPutRequestAction,
} from '@/ui5-components';
import { WeApiUrl, WeDataKey } from '@/store/generic-data/setup';

/**
 * This is the real "low-level" implementation of each GET request.
 * The `action` parameter is used as key to create the URL, set the loading status and report the response for the correct key.
 * @param action The key of the action
 */
function* getData(action: GenericGetRequestAction<WeDataKey>): any {
  try {
    const genericUrl = WeApiUrl(action.payload.key, action.payload.params);
    if (genericUrl) {
      yield put(UiActions.setLoading(action.payload.key, true));
      const apiUrl: string = getApiUrl(genericUrl, action.payload.queryParams);

      const { data, response } = yield call(fetchGet, apiUrl);
      yield put(UiActions.setLoading(action.payload.key, false));
      yield put(
        GenericDataActions.getResponse(
          action.payload.key,
          response === 200 ? data : undefined,
          response
        )
      );
    }
  } catch (e) {
    console.log('saga error', { e });
    yield put(GenericDataActions.getResponse(action.payload.key, undefined, 400));
    yield put(UiActions.setLoading(action.payload.key, false));
  }
}

function* postData(action: GenericPostRequestAction<WeDataKey>): any {
  const append = !!action.payload.append;
  // Append loads get their own loading flag (analogous to the POST suffix), so
  // "load more" and a regular replace can be distinguished in the UI.
  const uiVal = `${action.payload.key}${append ? 'APPEND' : FetchMethods.POST}`;
  // Echoed in the response action: the reducer applies a response only while
  // this is still the latest request signature for the key.
  const signature = {
    params: action.payload.params,
    queryParams: action.payload.queryParams,
    append,
  };
  try {
    const genericUrl = WeApiUrl(action.payload.key, action.payload.params, FetchMethods.POST);
    if (genericUrl) {
      yield put(UiActions.setLoading(uiVal, true));
      const apiUrl: string = getApiUrl(genericUrl, undefined);
      const { data, response } = yield call(
        fetchPost,
        apiUrl,
        action.payload.body,
        action.payload.queryParams,
        action.payload.responseType,
        action.payload.onUploadProgress
      );
      yield put(UiActions.setLoading(uiVal, false));
      yield put(GenericDataActions.postResponse(action.payload.key, response, data, signature));
    }
  } catch (e: any) {
    console.log('saga error', { e });
    yield put(
      GenericDataActions.postResponse(
        action.payload.key,
        // Network errors have no response object — report 400 like getData does,
        // otherwise the failure would be invisible in the store.
        e.response?.status ?? 400,
        e.response?.data,
        signature
      )
    );
    yield put(UiActions.setLoading(uiVal, false));
  }
}

function* putData(action: GenericPutRequestAction<WeDataKey>): any {
  const uiVal = `${action.payload.key}${FetchMethods.PUT}`;
  try {
    const genericUrl = WeApiUrl(action.payload.key, action.payload.params, FetchMethods.PUT);
    if (genericUrl) {
      yield put(UiActions.setLoading(uiVal, true));
      const apiUrl: string = getApiUrl(genericUrl);
      const { response } = yield call(fetchPut, apiUrl, action.payload.body);
      yield put(UiActions.setLoading(uiVal, false));
      yield put(GenericDataActions.putResponse(action.payload.key, response));
    }
  } catch (e) {
    console.log('saga error', e);
    yield put(GenericDataActions.putResponse(action.payload.key, 400));
    yield put(UiActions.setLoading(uiVal, false));
  }
}

function* deleteData(action: GenericDeleteRequestAction<WeDataKey>): any {
  const uiVal = `${action.payload.key}${FetchMethods.DELETE}`;
  try {
    const genericUrl = WeApiUrl(action.payload.key, action.payload.params, FetchMethods.DELETE);
    if (genericUrl) {
      yield put(UiActions.setLoading(uiVal, true));
      const apiUrl: string = getApiUrl(genericUrl);
      const { response } = yield call(fetchDel, apiUrl);
      yield delay(1000);
      yield put(UiActions.setLoading(uiVal, false));
      yield put(GenericDataActions.deleteResponse(action.payload.key, response));
    }
  } catch (e) {
    console.log('saga error', e);
    yield put(GenericDataActions.deleteResponse(action.payload.key, 400));
    yield put(UiActions.setLoading(uiVal, false));
  }
}

export default function* genericDataSaga(): any {
  yield all([
    (function* () {
      yield takeEvery(GenericDataActionType.GET_DATA_REQUEST, getData);
      yield takeEvery(GenericDataActionType.POST_DATA_REQUEST, postData);
      yield takeEvery(GenericDataActionType.PUT_DATA_REQUEST, putData);
      yield takeEvery(GenericDataActionType.DELETE_DATA_REQUEST, deleteData);
    })(),
  ]);
}
