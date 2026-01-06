// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useRef, useState } from 'react';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import { Outlet } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { getLoginState } from '@/store/auth/actions';
import { BusyIndicator, IllustrationMessageType } from '@ui5/webcomponents-react';
import { login, logout } from '@/services/AuthService';
import { PcErrorView } from '@/ui5-components';
import { interceptFetch } from '@/auth/AuthFetchInterceptor';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { useTranslation } from '@/i18n';

export const AuthWrapper: React.FC = props => {
  const { t, changeLanguage } = useTranslation();
  const loginState = useSelector((state: State) => state.auth.loginState);
  const userSettings = useSelector((state: State) => state.data[WeDataKey.USER_SETTINGS]);
  const dispatch = useDispatch();
  const [retries, setRetries] = useState(0);
  const userSettingsRequested = useRef(false);
  const userSettingsBootstrapped = useRef(false);

  const loggedInAndAuthorized = loginState?.data?.is_logged_in && loginState.data?.can_access_wf;
  const loggedInAndNotAuthorized =
    loginState?.data?.is_logged_in && !loginState.data?.can_access_wf;
  const loadingLoginStateFailed = loginState.response !== 200 && retries >= 2;
  const loadingUserSettings =
    loggedInAndAuthorized && !userSettingsBootstrapped.current && userSettings?.response === undefined;

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
      if (!userSettingsRequested.current) {
        userSettingsRequested.current = true;
        dispatch(getRequest(WeDataKey.USER_SETTINGS));
      }
    }
  }, [loginState]);

  useEffect(() => {
    if (userSettings?.response === 200 && userSettings.data?.locale) {
      changeLanguage(userSettings.data.locale);
    }
  }, [userSettings?.response, userSettings?.data?.locale, changeLanguage]);

  useEffect(() => {
    if (!userSettingsBootstrapped.current && userSettings?.response !== undefined) {
      userSettingsBootstrapped.current = true;
    }
  }, [userSettings?.response]);

  if (loginState.data && !loginState.data?.is_logged_in) {
    login();
  }

  if (loadingUserSettings) {
    return (
      <div className="flex inset-0 absolute items-center justify-center">
        <BusyIndicator active delay={100} />
      </div>
    );
  }

  if (loggedInAndAuthorized) return <Outlet />;
  if (loggedInAndNotAuthorized)
    return (
      <PcErrorView
        showReload={false}
        showHome={false}
        titleText={t('auth.missingAuthTitle')}
        subtitleText={t('auth.missingAuthSubtitle')}
        showLogout={true}
        onLogout={logout}
      />
    );
  if (loadingLoginStateFailed)
    return (
      <PcErrorView
        showReload={true}
        showHome={false}
        titleText={t('auth.connectionErrorTitle')}
        subtitleText={t('auth.connectionErrorSubtitle')}
        illustration={IllustrationMessageType.Connection}
      />
    );

  return (
    <div className="flex inset-0 absolute items-center justify-center">
      <BusyIndicator active delay={100} />
    </div>
  );
};
