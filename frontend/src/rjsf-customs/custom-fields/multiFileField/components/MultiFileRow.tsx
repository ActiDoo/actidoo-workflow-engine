// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { BusyIndicator, BusyIndicatorSize, Icon, Text } from '@ui5/webcomponents-react';
import React, { useState } from 'react';
import { useDispatch } from 'react-redux';
import { loadAndShowFile } from '@/services/HelperService';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { useParams } from 'react-router-dom';
import { PcFile } from '@/rjsf-customs/custom-fields/multiFileField/CustomMultiFileField';

interface MultiFileRowProps {
  file: PcFile;
  disabled: boolean;
  onRemove: () => void;
}
export const MultiFileRow: React.FC<MultiFileRowProps> = props => {
  const dispatch = useDispatch();
  const [isLoading, setIsLoading] = useState(false);

  const downloadFile = (file: PcFile): void => {
    if (file.hash) {
      setIsLoading(() => true);
      loadAndShowFile('user/download_attachment', { hash: file.hash })
        .catch(() => {
          dispatch(
            addToast(
              <WeToastContent text="An error occurred while loading the file" type="error" />
            )
          );
        })
        .finally(() => {
          setIsLoading(() => false);
        });
    }
  };

  return (
    <div
      className={`flex items-center justify-between py-2 px-3 border-solid border-1 border-neutral-200 rounded mb-2 bg-neutral-50 `}>
      <Text className={`${props.disabled ? '!text-neutral-700' : ''}`}>{props.file.filename}</Text>
      <div className="flex gap-3 items-center">
        {isLoading ? <BusyIndicator active delay={0} size={BusyIndicatorSize.Small} /> : null}
        {props.file.hash && (
          <Icon
            name="download"
            className={`cursor-pointer text-brand-primary ${
              isLoading ? 'pointer-events-none opacity-30' : ''
            }`}
            onClick={() => {
              downloadFile(props.file);
            }}
          />
        )}
        {!props.disabled && (
          <Icon
            name="delete"
            className="cursor-pointer text-accent-negative"
            onClick={() => {
              props.onRemove();
            }}
          />
        )}
      </div>
    </div>
  );
};
