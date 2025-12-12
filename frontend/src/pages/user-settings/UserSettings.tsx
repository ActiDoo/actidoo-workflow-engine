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

const supportedLocales = [
  { key: 'en', label: 'English' },
  { key: 'de', label: 'German' },
  // add more locales as needed
];

const UserSettings: React.FC = () => {
  const key = WeDataKey.USER_SETTINGS;
  const dispatch = useDispatch();
  const data = useSelector((state: State) => state.data[key]);
  const options = data?.data?.supported_locales || [];

  const [locale, setLocale] = useState<string>('');

  // Load settings on mount
  useEffect(() => {
    dispatch(getRequest(key));
  }, [dispatch, key]);

  // Update local state when data arrives
  useEffect(() => {
    if (data?.data?.locale) {
      setLocale(data.data.locale);
    }
  }, [data?.data]);

  const handleSave = () => {
    dispatch(postRequest(key, { locale }));
  };

  return (
    <PcPage header={{ title: 'User Settings' }}>
      <FlexBox className="items-center mb-4" alignItems={FlexBoxAlignItems.Center}>
        <Label className="mr-2">Your preferred localization language for workflows: </Label>
        <Select
          className="w-48"
          onChange={(e) => setLocale(e.detail.selectedOption.getAttribute('data-key') || '')}
        >
          {options.map(({ key, label }) => (
            <Option key={key} data-key={key} selected={key === locale}>
              {label}
            </Option>
          ))}
        </Select>
      </FlexBox>
      <div>
        <Label className="mr-2">
          This setting only affects upcoming workflows and only if they are available in multiple languages.
          <br></br>
          The overall user interface of the Workflow Engine is also not affected by this setting and only available in English at the moment.
        </Label>
      </div>

      <Button className="mt-4" design="Emphasized" onClick={handleSave}>
        Save Settings
      </Button>
    </PcPage>
  );
};

export default UserSettings;
