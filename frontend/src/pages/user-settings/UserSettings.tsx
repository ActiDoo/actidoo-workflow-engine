// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';

import { PcPage } from '@/ui5-components';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import {
  Select,
  Option,
  Label,
  Button,
  FlexBox,
  FlexBoxAlignItems
} from '@ui5/webcomponents-react';
import { useTranslation } from '@/i18n';

const UserSettings: React.FC = () => {
  const { t, changeLanguage, availableLanguages } = useTranslation();
  const key = WeDataKey.USER_SETTINGS;
  const dispatch = useDispatch();
  const data = useSelector((state: State) => state.data[key]);
  const options = data?.data?.supported_locales?.length
    ? data.data.supported_locales
    : availableLanguages.map(lang => ({ key: lang.key, label: lang.label }));

  const [locale, setLocale] = useState<string>('');

  // Load settings on mount
  useEffect(() => {
    dispatch(getRequest(key));
  }, [dispatch, key]);

  // Update local state when data arrives
  useEffect(() => {
    if (data?.data?.locale) {
      setLocale(data.data.locale);
      changeLanguage(data.data.locale);
    }
  }, [data?.data, changeLanguage]);

  const handleSave = () => {
    changeLanguage(locale);
    dispatch(postRequest(key, { locale }));
  };

  return (
    <PcPage header={{ title: t('userSettings.title') }}>
      <FlexBox className="items-center mb-4" alignItems={FlexBoxAlignItems.Center}>
        <Label className="mr-2">{t('userSettings.localeLabel')}</Label>
        <Select
          className="w-48"
          onChange={e => {
            const nextLocale = e.detail.selectedOption.getAttribute('data-key') || '';
            setLocale(nextLocale);
            changeLanguage(nextLocale);
          }}
        >
          {options.map(({ key, label }) => (
            <Option key={key} data-key={key} selected={key === locale}>
              {label}
            </Option>
          ))}
        </Select>
      </FlexBox>
      <div>
        <Label className="mr-2">{t('userSettings.localeHint')}</Label>
      </div>

      <Button className="mt-4" design="Emphasized" onClick={handleSave}>
        {t('userSettings.save')}
      </Button>
    </PcPage>
  );
};

export default UserSettings;
