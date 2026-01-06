// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { PropsWithChildren } from 'react';
import { useNavigate } from 'react-router-dom';

import { Icon, Link, Title } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/log';
import { PcPageHeaderData } from '@/ui5-components/lib/pc-page/PcPage';
import { PcSearch } from '@/ui5-components/lib/pc-search/PcSearch';

export interface PcPageHeaderProps extends PropsWithChildren {
  header?: PcPageHeaderData;
}

export const PcPageHeader: React.FC<PcPageHeaderProps> = props => {
  const navigate = useNavigate();
  const { header } = props;
  const handleNavigateBack = (): void => {
    if (header?.forceBackTo) navigate(header.forceBackTo);
    else navigate(-1);
  };
  return (
    <div className="bg-white pc-px-responsive py-6 sticky z-[80] top-0 sapContent_Shadow0">
      <div className="flex items-center flex-wrap gap-2">
        {header?.showBack && (
          <Link
            onClick={() => {
              handleNavigateBack();
            }}>
            <Icon name="nav-back" className="w-8 h-full -ml-2" />
          </Link>
        )}
        <Title className="flex-1">{header?.title}</Title>

        <div className="flex items-center gap-4">
          {header?.searchInput && (
            <PcSearch initialSearch={header?.initialSearch} searchInput={header?.searchInput} />
          )}
          {header?.actionSection && header?.searchInput && (
            <div className="mx-2 border-r border-pc-gray-400 border-r-solid h-8" />
          )}
          {header?.actionSection && <div className="flex gap-4">{header?.actionSection}</div>}
        </div>
      </div>
    </div>
  );
};
