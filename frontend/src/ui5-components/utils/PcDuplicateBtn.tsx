// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Icon } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/duplicate';
import { useTranslation } from '@/i18n';

interface PcDuplicateBtnProps {
  onDuplicate: () => any;
  disabled?: boolean;
}
export const PcDuplicateBtn: React.FC<PcDuplicateBtnProps> = props => {
  const { t } = useTranslation();
  return (
    <div
      onClick={() => {
        props.onDuplicate();
      }}
      className="w-full text-center cursor-pointer ">
      <Icon
        accessibleName={t('common.actions.duplicate')}
        name="duplicate"
        showTooltip={true}
        className={
          'w-5 h-full ' +
          (props.disabled ? 'text-gray-300 cursor-default' : ' hover:text-brand-primary-strong ')
        }
      />
    </div>
  );
};
