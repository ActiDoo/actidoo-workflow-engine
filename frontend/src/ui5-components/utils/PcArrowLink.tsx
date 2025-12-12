import { Icon } from '@ui5/webcomponents-react';
import React from 'react';
import { Link } from 'react-router-dom';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';

interface PcArrowLinkProps {
  link?: string;
  disabled?: boolean;
  replace?: boolean;
  onClick?: () => {};
}
export const PcArrowLink: React.FC<PcArrowLinkProps> = props => {
  const icon = (
    <Icon
      name="navigation-right-arrow"
      accessibleName="Show details"
      showTooltip={true}
      className={
        'w-6 h-full ' +
        (props.disabled ? 'text-gray-300 cursor-default' : ' hover:text-brand-primary-strong ')
      }
    />
  );
  return props.link ? (
    <Link to={props.link} replace={props.replace} className="w-full text-center ">
      {icon}
    </Link>
  ) : (
    <div
      className="cursor-pointer w-full text-center "
      onClick={() => (props.onClick ? props.onClick() : null)}>
      {icon}
    </div>
  );
};
