// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';

import {
  Button,
  ButtonDesign,
  IllustratedMessage,
  IllustrationMessageType,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-fiori/dist/illustrations/SimpleError.js';
import '@ui5/webcomponents-fiori/dist/illustrations/Connection.js';
import { useTranslation } from '@/i18n';

interface ErrorViewProps {
  titleText?: string;
  subtitleText?: string;
  illustration?: IllustrationMessageType.SimpleError | IllustrationMessageType.Connection;
  showReload?: boolean;
  showHome?: boolean;
  showLogout?: boolean;
  onLogout?: Function;
}

export const PcErrorView: React.FC<ErrorViewProps> = props => {
  const { t } = useTranslation();
  const {
    titleText = t('errorView.defaultTitle'),
    subtitleText = t('errorView.defaultSubtitle'),
    illustration = IllustrationMessageType.SimpleError,
    showReload = true,
    showHome = true,
    showLogout = false,
    onLogout,
  } = props;
  return (
    <div className="absolute inset-0 flex  flex-col items-center justify-center bg-pc-gray-50">
      <div className="bg-white p-16 max-w-4xl mb-32 text-center">
        <IllustratedMessage name={illustration} titleText={titleText} subtitleText={subtitleText} />
        <div className="flex gap-2 items-center justify-center">
          {showReload && (
            <Button
              onClick={() => {
                window.location.reload();
              }}
              design={ButtonDesign.Emphasized}>
              {t('errorView.tryAgain')}
            </Button>
          )}
          {showHome && (
            <Button
              onClick={() => {
                window.location.pathname = '';
              }}
              design={ButtonDesign.Emphasized}>
              {t('errorView.goHome')}
            </Button>
          )}
          {showLogout && (
            <Button
              onClick={() => {
                if (onLogout) onLogout();
              }}
              design={ButtonDesign.Emphasized}>
              {t('errorView.logout')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
