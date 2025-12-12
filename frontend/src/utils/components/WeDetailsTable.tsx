import { Text } from '@ui5/webcomponents-react';
import React, { ReactNode } from 'react';

interface WeDetailsTableProps {
  data: Array<{ label: string; content: string | ReactNode | undefined }>;
}

export const WeDetailsTable: React.FC<WeDetailsTableProps> = props => {
  return (
    <table>
      <tbody>
        {props.data.map((row, index) => (
          <tr key={`we-details-table-${index}-${row.label.replace(' ', '')}`}>
            <td className="pr-2">
              <Text className="!text-gray-500 !whitespace-nowrap">{row.label}: </Text>
            </td>
            <td className="w-full">
              <Text>{row?.content ? row?.content : '-'}</Text>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};
