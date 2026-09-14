// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { ReactElement } from 'react';
import React from 'react';
import { ArrayFieldItemTemplateProps, getUiOptions } from '@rjsf/utils';
import { PcIconButton } from '@/ui5-components';
import { useTranslation } from '@/i18n';
import '@ui5/webcomponents-icons/dist/duplicate';
import '@ui5/webcomponents-icons/dist/navigation-up-arrow';

const CustomArrayFieldItemTemplate = (props: ArrayFieldItemTemplateProps): ReactElement => {
  const { t } = useTranslation();
  const { buttonsProps, children, className, disabled, index, parentUiSchema } = props;

  const uiOptions = getUiOptions(parentUiSchema);
  const allowAddRemove = String((uiOptions as any)?.arrayAllowAddRemove ?? 'True') === 'True';

  return (
    <div className={` relative m-4  ${className} `}>
      <div className="flex gap-2 items-center justify-end">
        <div className="flex-1 ">
          <div className="bg-neutral-100  z-10 text-brand-primary font-semibold aspect-square rounded  w-8 h-8 flex items-center justify-center">
            {`${index + 1}`}
          </div>
        </div>
        {allowAddRemove && buttonsProps.hasMoveDown && (
          <PcIconButton
            icon="navigation-down-arrow"
            tooltip={t('common.actions.moveDown')}
            onClick={buttonsProps.onMoveDownItem}
            disabled={disabled}
          />
        )}
        {allowAddRemove && buttonsProps.hasMoveUp && (
          <PcIconButton
            icon="navigation-up-arrow"
            tooltip={t('common.actions.moveUp')}
            onClick={buttonsProps.onMoveUpItem}
            disabled={disabled}
          />
        )}
        {allowAddRemove && buttonsProps.hasCopy && (
          <PcIconButton
            icon="duplicate"
            tooltip={t('common.actions.duplicate')}
            onClick={buttonsProps.onCopyItem}
            disabled={disabled}
          />
        )}
        {allowAddRemove && buttonsProps.hasRemove && (
          <PcIconButton
            icon="delete"
            negative={true}
            tooltip={t('common.actions.delete')}
            onClick={buttonsProps.onRemoveItem}
            disabled={disabled}
          />
        )}
      </div>
      <div className="pt-4 pl-8">{children}</div>
    </div>
  );
};

export default CustomArrayFieldItemTemplate;
