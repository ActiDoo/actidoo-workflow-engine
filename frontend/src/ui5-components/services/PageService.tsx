import { PcSortItem, StringDict, TableQueryParams } from '../models/models';
import { AdditionalTableData } from '../hooks/useAdditionalTableFunctions';

export function calculatePageOffset(currentPage?: number, limit?: number): number {
  return currentPage && limit ? limit * currentPage : 0;
}
export function calculateInitialPage(offset?: number, limit?: number): number {
  return limit && offset && offset > 0 ? offset / limit : 0;
}

export function getTableDataFromQueryParams(
  queryParams?: StringDict
): [number, string, StringDict, PcSortItem | undefined] {
  const offset = queryParams ? Number(queryParams[TableQueryParams.OFFSET]) : 0;
  const search = queryParams ? queryParams[TableQueryParams.SEARCH] : '';
  const sort = queryParams ? queryParams[TableQueryParams.SORT] : '';
  let sortItem: PcSortItem | undefined;
  if (sort) {
    const splitted = sort.split('.');
    sortItem =
      splitted[0] && splitted[1] ? { id: splitted[0], sortDirection: splitted[1] } : undefined;
  }
  const filter: StringDict = {};
  for (const key in queryParams) {
    if (key.includes('f_')) {
      // debugger;
      filter[key.replace('f_', '')] = queryParams[key];
    }
  }
  return [offset, search, filter, sortItem];
}

export function getQueryParamsFromTableData(
  tableData?: AdditionalTableData,
  limit?: number
): StringDict {
  const finalFilter: StringDict = {};

  for (const key in tableData?.filter) {
    if (tableData?.filter[key] !== undefined && tableData?.filter[key] !== '') {
      finalFilter['f_' + accessorToQueryParam(key)] = tableData.filter[key];
    }
  }

  const finalParams: StringDict = {};
  if (tableData?.offset) finalParams[TableQueryParams.OFFSET] = tableData.offset;
  if (tableData?.search) finalParams[TableQueryParams.SEARCH] = tableData.search;
  if (tableData?.sort)
    finalParams[TableQueryParams.SORT] = `${accessorToQueryParam(tableData.sort.id)}.${
      tableData?.sort.sortDirection
    }`;
  if (limit) finalParams[TableQueryParams.LIMIT] = limit;

  return {
    ...finalParams,
    ...finalFilter,
  };
}

export const accessorToQueryParam = (val: string): string => val.replace(/\./g, '___');
export const queryParamToAccessor = (val: string): string => val.replace(/___/g, '.');
