// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { all, call, put, takeLatest } from 'redux-saga/effects';
import * as UiActions from '@/store/ui/actions';
import * as AuthActions from '@/store/auth/actions';

import { getAuthApiUrl } from '@/services/ApiService';
import { SimpleActionInput, fetchGet } from '@/ui5-components';
import { AuthActionType } from '@/store/auth/setup';

function* getLoginState(action: SimpleActionInput): any {
  try {
    yield put(UiActions.setLoading(action.type, true));
    const apiUrl: string = getAuthApiUrl('get_login_state');
    const { data, response } = yield call(fetchGet, apiUrl);
    yield put(UiActions.setLoading(action.type, false));
    yield put(AuthActions.setLoginState(response === 200 ? data : undefined, response));
  } catch (e) {
    console.log('saga error', { e });
    yield put(AuthActions.setLoginState(undefined, 400));
    yield put(UiActions.setLoading(action.type, false));
  }
}

export default function* authSaga(): any {
  yield all([
    (function* () {
      yield takeLatest(AuthActionType.GET_LOGIN_STATE, getLoginState);
    })(),
  ]);
}
