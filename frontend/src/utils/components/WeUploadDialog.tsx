// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { BusyIndicator, Dialog, ProgressIndicator, Text } from '@ui5/webcomponents-react';
import React from 'react';
import { createPortal } from 'react-dom';

export const WeUploadDialog: React.FC<{
  isOpen: boolean;
  progress: number;
  progressLabel?: string | undefined;
  processLabel?: string | undefined;
}> = props => {
  return createPortal(
    <Dialog
      open={props.isOpen}
      // Progress dialog: ESC must not dismiss it mid-upload. Programmatic close
      // (isOpen=false) fires the same cancelable before-close with escPressed=false
      // and must proceed — an unconditional preventDefault would stick it open.
      onBeforeClose={e => {
        if (e.detail.escPressed) e.preventDefault();
      }}>
      <div className="p-4 h-[150px] flex flex-col items-center justify-center">
        {props.progress !== 100 ? (
          <div className="flex flex-col gap-3 text-center">
            <ProgressIndicator className="mt-3 !pr-0" value={props.progress} />
            <Text>{props.progressLabel ?? ''}</Text>
          </div>
        ) : (
          <div className="flex flex-col gap-3 text-center">
            <BusyIndicator active delay={0} />
            <Text>{props.progressLabel ?? ''}</Text>
          </div>
        )}
      </div>
    </Dialog>,
    document.body
  );
};
