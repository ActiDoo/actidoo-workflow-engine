import React, { useEffect, useState } from 'react';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import { Outlet } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { getLoginState } from '@/store/auth/actions';
import { BusyIndicator, IllustrationMessageType } from '@ui5/webcomponents-react';
import { login, logout } from '@/services/AuthService';
import { PcErrorView } from '@/ui5-components';
import { interceptFetch } from '@/auth/AuthFetchInterceptor';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';

export const AuthWrapper: React.FC = props => {
  const loginState = useSelector((state: State) => state.auth.loginState);
  const dispatch = useDispatch();
  const [retries, setRetries] = useState(0);

  const loggedInAndAuthorized = loginState?.data?.is_logged_in && loginState.data?.can_access_wf;
  const loggedInAndNotAuthorized =
    loginState?.data?.is_logged_in && !loginState.data?.can_access_wf;
  const loadingLoginStateFailed = loginState.response !== 200 && retries >= 2;

  useEffect(() => {
    interceptFetch();
    dispatch(getLoginState());
  }, []);

  useEffect(() => {
    if (loginState.response && loginState.response !== 200 && retries < 2) {
      setRetries(r => {
        return r + 1;
      });
      dispatch(getLoginState());
    }
    if (loginState.response === 200) {
      dispatch(postRequest(WeDataKey.WFE_USER, {}));
    }
  }, [loginState]);

  if (loginState.data && !loginState.data?.is_logged_in) {
    login();
  }

  if (loggedInAndAuthorized) return <Outlet />;
  if (loggedInAndNotAuthorized)
    return (
      <PcErrorView
        showReload={false}
        showHome={false}
        titleText="Missing authentication"
        subtitleText="You are not allowed to access this site."
        showLogout={true}
        onLogout={logout}
      />
    );
  if (loadingLoginStateFailed)
    return (
      <PcErrorView
        showReload={true}
        showHome={false}
        titleText="Could not connect to server "
        subtitleText="Something went wrong while connecting the server. Please try again."
        illustration={IllustrationMessageType.Connection}
      />
    );

  return (
    <div className="flex inset-0 absolute items-center justify-center">
      <BusyIndicator active delay={100} />
    </div>
  );
};
