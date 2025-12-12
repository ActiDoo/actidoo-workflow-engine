import { ReactNode } from 'react';
import { UiAction, UiActionType } from '@/store/ui/setup';
import { DialogPropTypes } from '@ui5/webcomponents-react';

// custom actions

export const setLoading = (id: string, loading: boolean): UiAction => {
  return {
    type: UiActionType.SET_LOADING,
    payload: { id, loading },
  };
};

export const addToast = (content: ReactNode): UiAction => {
  return {
    type: UiActionType.ADD_TOAST,
    payload: { content },
  };
};

export const setDialog = (props?: DialogPropTypes): UiAction => {
  return {
    type: UiActionType.SET_DIALOG,
    payload: { props },
  };
};
