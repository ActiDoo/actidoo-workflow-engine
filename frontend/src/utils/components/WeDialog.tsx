// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Dialog } from '@ui5/webcomponents-react';
import React from 'react';
import { useSelector } from 'react-redux';
import { State } from '@/store';

export const WeDialog: React.FC = () => {
  const dialogProps = useSelector((state: State) => state.ui.dialog);
  return <Dialog {...dialogProps}></Dialog>;
};
