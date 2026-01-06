// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { ReactElement } from 'react';
import React from 'react';
import { ArrayFieldItemTemplateProps, getUiOptions } from '@rjsf/utils';
import { Button, ButtonDesign } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/duplicate';
import '@ui5/webcomponents-icons/dist/navigation-up-arrow';

const CustomArrayFieldItemTemplate = (props: ArrayFieldItemTemplateProps): ReactElement => {
  const { buttonsProps, children, className, disabled, index, parentUiSchema } = props;

  const uiOptions = getUiOptions(parentUiSchema);
  const allowAddRemove = String((uiOptions as any)?.arrayAllowAddRemove ?? 'True') === 'True';

  return (
    <div className={` relative m-4  ${className} `}>
      <div className="flex gap-2 items-center justify-end">
        <div className="flex-1 ">
          <div className="bg-neutral-100  z-10 text-brand-primary font-fold aspect-square rounded  w-8 h-8 flex items-center justify-center">
            {`${index + 1}`}
          </div>
        </div>
        {allowAddRemove && buttonsProps.hasMoveDown && (
          <Button
            icon="navigation-down-arrow"
            onClick={buttonsProps.onMoveDownItem}
            design={ButtonDesign.Transparent}
            disabled={disabled}>
          </Button>
        )}
        {allowAddRemove && buttonsProps.hasMoveUp && (
          <Button
            icon="navigation-up-arrow"
            design={ButtonDesign.Transparent}
            onClick={buttonsProps.onMoveUpItem}
            disabled={disabled}>
          </Button>
        )}
        {allowAddRemove && buttonsProps.hasCopy && (
          <Button
            icon="duplicate"
            design={ButtonDesign.Transparent}
            onClick={buttonsProps.onCopyItem}
            disabled={disabled}>
          </Button>
        )}
        {allowAddRemove && buttonsProps.hasRemove && (
          <Button
            icon="delete"
            design={ButtonDesign.Negative}
            onClick={buttonsProps.onRemoveItem}
            disabled={disabled}>
          </Button>
        )}
      </div>
      <div className="pt-4 pl-8">{children}</div>
    </div>
  );
};

export default CustomArrayFieldItemTemplate;

