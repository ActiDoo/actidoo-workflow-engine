import React from 'react';
import {
  BusyIndicator,
  BusyIndicatorSize,
  Dialog,
  Icon,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import { createPortal } from 'react-dom';

interface AlertDialogProps {
  title?: string;
  buttons?: React.ReactElement;
  isLoading?: boolean;
  isDialogOpen?: boolean;
  setDialogOpen: (isOpen: boolean) => void;
  children?: React.ReactElement;
}

const WeAlertDialog: React.FC<AlertDialogProps> = props => {
  return createPortal(
    <Dialog
      open={props.isDialogOpen}
      header={
        <div className="w-full flex items-center gap-2">
          <Title level={TitleLevel.H5} className="w-full py-2">
            {props.title ?? ''}
          </Title>
          <Icon
            className="cursor-pointer "
            name="decline"
            onClick={() => {
              props.setDialogOpen(false);
            }}
          />
        </div>
      }
      footer={<div className="w-full flex justify-end gap-2 mt-2">{props.buttons}</div>}>
      <BusyIndicator
        active={props.isLoading}
        delay={0}
        size={BusyIndicatorSize.Small}
        className="bg-white/80 w-full">
        <div className="w-full flex flex-column">{props.children}</div>
      </BusyIndicator>
    </Dialog>,
    document.body
  );
};
export default WeAlertDialog;
