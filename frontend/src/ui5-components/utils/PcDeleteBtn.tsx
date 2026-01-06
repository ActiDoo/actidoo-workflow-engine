// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Icon } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/delete';
import { useTranslation } from '@/i18n';

interface PcDeleteBtnProps {
  onDelete: () => any;
  disabled?: boolean;
}
export const PcDeleteBtn: React.FC<PcDeleteBtnProps> = props => {
  const { t } = useTranslation();
  return (
    <div
      onClick={() => {
        props.onDelete();
      }}
      className="w-full text-center cursor-pointer ">
      <Icon
        name="delete"
        accessibleName={t('common.actions.delete')}
        showTooltip={true}
        className={
          'w-5 h-full ' +
          (props.disabled ? 'text-gray-300 cursor-default' : ' hover:text-brand-primary-strong ')
        }
      />
    </div>
  );
};
