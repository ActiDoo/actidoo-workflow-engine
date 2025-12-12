import { Dialog } from '@ui5/webcomponents-react';
import React from 'react';
import { useSelector } from 'react-redux';
import { State } from '@/store';

export const WeDialog: React.FC = () => {
  const dialogProps = useSelector((state: State) => state.ui.dialog);
  return <Dialog {...dialogProps}></Dialog>;
};
