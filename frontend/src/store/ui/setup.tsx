// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { ReactNode } from 'react';
import { DialogPropTypes } from '@ui5/webcomponents-react';

// STATE DEFINITION
export interface UiState {
  loading: Record<string, boolean>;
  toast: ReactNode | undefined;
  dialog: DialogPropTypes | undefined;
}

// ACTION DEFINITIONS
export enum UiActionType {
  SET_LOADING = 'UI_SET_LOADING',
  ADD_TOAST = 'UI_ADD_TOAST',
  SET_DIALOG = 'UI_SET_DIALOG',
}

interface UiSetLoadingAction {
  type: UiActionType.SET_LOADING;
  payload: {
    id: string;
    loading: boolean;
  };
}

interface UiAddToastAction {
  type: UiActionType.ADD_TOAST;
  payload: {
    content: ReactNode;
  };
}
interface UiSetDialogAction {
  type: UiActionType.SET_DIALOG;
  payload: {
    props?: DialogPropTypes;
  };
}
export type UiAction = UiSetLoadingAction | UiAddToastAction | UiSetDialogAction;
