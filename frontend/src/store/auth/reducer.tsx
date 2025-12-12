import { AuthAction, AuthActionType, AuthState } from '@/store/auth/setup';

const initState: AuthState = {
  loginState: { data: undefined, response: undefined },
  loginUrl: undefined,
};

export default (state = initState, action: AuthAction): AuthState => {
  switch (action.type) {
    case AuthActionType.SET_LOGIN_STATE:
      return {
        ...state,
        loginState: action.payload,
      };
    case AuthActionType.RESET_ACCESS_DPF:
      return {
        ...state,
        loginState: {
          ...state.loginState,
          data: {
            ...state.loginState.data,
            can_access_wf: false,
          },
        },
      };

    default:
      return state;
  }
};
