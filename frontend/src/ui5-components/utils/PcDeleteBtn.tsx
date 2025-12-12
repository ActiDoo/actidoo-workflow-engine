import { Icon } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/delete';

interface PcDeleteBtnProps {
  onDelete: () => any;
  disabled?: boolean;
}
export const PcDeleteBtn: React.FC<PcDeleteBtnProps> = props => {
  return (
    <div
      onClick={() => {
        props.onDelete();
      }}
      className="w-full text-center cursor-pointer ">
      <Icon
        name="delete"
        accessibleName="Delete"
        showTooltip={true}
        className={
          'w-5 h-full ' +
          (props.disabled ? 'text-gray-300 cursor-default' : ' hover:text-brand-primary-strong ')
        }
      />
    </div>
  );
};
