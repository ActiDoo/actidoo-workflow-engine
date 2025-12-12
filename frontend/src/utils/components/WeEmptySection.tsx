import React from 'react';
import { Icon, IconDesign, Text, Title } from '@ui5/webcomponents-react';

interface WeEmptySectionProps {
  icon: string;
  title: string;
  text: string;
}
export const WeEmptySection: React.FC<WeEmptySectionProps> = props => {
  return (
    <div className="flex items-center justify-center h-full flex-col gap-3 text-center p-16">
      <Icon name={props.icon} design={IconDesign.Neutral} className=" w-12 h-12 " />
      <div>
        <Title level="H4">{props.title}</Title>
        <Text>{props.text}</Text>
      </div>
    </div>
  );
};
