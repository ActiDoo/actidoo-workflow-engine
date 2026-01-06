// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useSelector } from 'react-redux';
import { type State } from '@/store';
import { Icon, Text, Toast, type ToastDomRef } from '@ui5/webcomponents-react';
import React, { type MutableRefObject, useEffect, useRef } from 'react';
import '@ui5/webcomponents-icons/dist/message-information.js';

export const WeToast: React.FC = () => {
  const toast = useSelector((state: State) => state.ui.toast);
  const ref = useRef<ToastDomRef>() as MutableRefObject<ToastDomRef> | undefined;

  useEffect(() => {
    ref?.current?.show();
  }, [toast]);

  return toast ? <Toast ref={ref}>{toast}</Toast> : <></>;
};

export const WeToastContent: React.FC<{ text: string; type?: 'success' | 'error' }> = props => {
  let icon = '';
  let color = '';
  switch (props.type) {
    case 'success':
      icon = 'message-success';
      color = '!text-brand-primary';
      break;
    case 'error':
      icon = 'message-error';
      color = '!text-accent-negative';
      break;
    default:
      icon = 'message-information';
      color = '!text-neutral-800';
  }

  return (
    <div className="flex items-center gap-2 text-left">
      <Icon name={icon} className={`${color} w-6 h-6`} />
      <Text className={`${color} !font-bold`}>{props.text}</Text>
    </div>
  );
};
