import { PcTableData } from '@/ui5-components/models/models';
import { AnalyticalTableColumnDefinition, InputType } from '@ui5/webcomponents-react';
import { PcAnalyticalTableHeader } from '@/ui5-components/lib/pc-analytical-table/PcAnalyticalTableHeader';
import { PcDateString } from '@/ui5-components/utils/PcDateString';
import { PcDateFilter } from '@/ui5-components/lib/pc-analytical-table/filter/PcDateFilter';
import React from 'react';
import { queryParamToAccessor } from '@/ui5-components/services/PageService';
import { PcInputFilter } from '@/ui5-components/lib/pc-analytical-table/filter/PcInputFilter';
import { Link } from 'react-router-dom';

function getValFromNestedElement(original: any, accessor: string): any {
  let final = original;
  const slitted = accessor.split('.');
  slitted.forEach(t => {
    final = final[t];
  });
  return final;
}
export const PcDateColumn = (
  accessor: string,
  headerName: string,
  tableData: PcTableData
): AnalyticalTableColumnDefinition => {
  return {
    accessor,
    Header: (data: any) => {
      const val = tableData.filter[`${data.column.id}_eq`] ?? '';
      return (
        <PcAnalyticalTableHeader
          name={headerName}
          filtered={!!val}
          sortDirection={tableData.sort?.id === accessor ? tableData.sort.sortDirection : undefined}
        />
      );
    },
    Cell: (instance: any) => {
      const val = getValFromNestedElement(instance.row.original, accessor);
      return <PcDateString val={val} />;
    },
    Filter: (data: any) => (
      <PcDateFilter onFilter={tableData.onFilter} column={data.column} filter={tableData.filter} />
    ),
    sortType: rowA => rowA,
  };
};

export const PcInputColumn = (
  accessor: string,
  headerName: string,
  tableData: PcTableData,
  type?: InputType.Number | InputType.Text,
  link?: {
    pre?: string;
    parts?: Array<{ value?: string; isInstanceValue?: boolean }>;
  }
): AnalyticalTableColumnDefinition => {
  const finalLink = (instance: any): string[] | undefined =>
    link?.parts
      ? link.parts.map(l =>
          l.isInstanceValue && l.value ? instance.row.original[l.value] : l.value
        )
      : undefined;
  return {
    Header: (data: any) => {
      const val =
        tableData.filter[`${data.column.id}${type === InputType.Number ? '_eq' : ''}`] ?? '';
      return (
        <PcAnalyticalTableHeader
          name={headerName}
          filtered={!!val}
          sortDirection={
            tableData.sort && queryParamToAccessor(tableData.sort?.id) === accessor
              ? tableData.sort.sortDirection
              : undefined
          }
        />
      );
    },
    accessor,
    Cell: (instance: any) => {
      const val = getValFromNestedElement(instance.row.original, accessor);
      return link ? (
        <Link
          to={`${link.pre ? link.pre : ''}${finalLink(instance)?.join('/')}`}
          className="text-pc-blue-primary ">
          {val}
        </Link>
      ) : (
        <>{val}</>
      );
    },

    Filter: (data: any) => {
      const val =
        tableData.filter[`${data.column.id}${type === InputType.Number ? '_eq' : ''}`] ?? '';
      return (
        <PcInputFilter
          onFilter={tableData.onFilter}
          column={data.column}
          val={val}
          type={type ?? InputType.Text}
        />
      );
    },
    sortType: rowA => rowA,
  };
};
