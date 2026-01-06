// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { LoginState, LoginUrl } from '@/models/models';

// STATE DEFINITION
export interface AuthState {
  loginState: {
    data: LoginState | undefined;
    response: number | undefined;
  };
  loginUrl: LoginUrl | undefined;
}

// ACTION DEFINITION
export enum AuthActionType {
  GET_LOGIN_STATE = 'AUTH_GET_LOGIN_STATE',
  SET_LOGIN_STATE = 'AUTH_SET_LOGIN_STATE',
  RESET_ACCESS_DPF = 'AUTH_RESET_ACCESS_DPF',
}
// Actions
interface SetLoginStateAction {
  type: AuthActionType.SET_LOGIN_STATE;
  payload: { data: LoginState | undefined; response: number };
}
interface ResetAccessDPFAction {
  type: AuthActionType.RESET_ACCESS_DPF;
}

export type AuthAction = SetLoginStateAction | ResetAccessDPFAction;
