import { Icon } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/download';

interface PcDownloadLinkProps {
  link: string;
}
export const PcDownloadLink: React.FC<PcDownloadLinkProps> = props => {
  const handleDownload = (): void => {
    window.open(props.link);
  };
  return (
    <div onClick={handleDownload} className="w-full text-center cursor-pointer">
      <Icon name="download" className="w-5 h-full  hover:text-brand-primary-strong " />
    </div>
  );
};
