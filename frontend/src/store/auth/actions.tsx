import { LoginState } from '@/models/models';
import { SimpleActionInput } from '@/ui5-components';
import { AuthAction, AuthActionType } from '@/store/auth/setup';

export const getLoginState = (): SimpleActionInput => {
  return {
    type: AuthActionType.GET_LOGIN_STATE,
  };
};

export const setLoginState = (data: LoginState | undefined, response: number): AuthAction => {
  return {
    type: AuthActionType.SET_LOGIN_STATE,
    payload: { data, response },
  };
};
