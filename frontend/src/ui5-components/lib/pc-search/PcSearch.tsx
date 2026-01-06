// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Button, ButtonDesign, Icon, Input } from '@ui5/webcomponents-react';
import React, { useState } from 'react';
import { useTranslation } from '@/i18n';

export interface PcSearchProps {
  initialSearch?: string;
  searchInput?: (val?: string) => void;
}

export const PcSearch: React.FC<PcSearchProps> = props => {
  const { t } = useTranslation();
  const { initialSearch, searchInput } = props;

  const [searchValue, setSearchValue] = useState(initialSearch ?? '');
  const [lastSearchValue, setLastSearchValue] = useState(initialSearch ?? '');

  const handleSearch = (): void => {
    sendVal(searchValue);
  };

  const handleReset = (): void => {
    setSearchValue('');
    sendVal('');
  };

  const handleKeyDown = (key: string): void => {
    if (key === 'Enter') sendVal(searchValue);
  };

  const sendVal = (val: string): void => {
    if (searchInput) searchInput(val);
    setLastSearchValue(val);
  };

  return (
    <>
      <Input
        icon={<Icon name="search" />}
        onInput={e => {
          setSearchValue(e.target.value ?? '');
        }}
        value={searchValue}
        onKeyDown={e => {
          handleKeyDown(e.key);
        }}
      />
      <Button
        disabled={searchValue === '' || lastSearchValue === searchValue}
        design={ButtonDesign.Emphasized}
        onClick={handleSearch}>
        {t('common.actions.search')}
      </Button>
      <Button
        disabled={searchValue === '' && lastSearchValue === ''}
        design={ButtonDesign.Transparent}
        onClick={handleReset}>
        {t('common.actions.reset')}
      </Button>
    </>
  );
};
