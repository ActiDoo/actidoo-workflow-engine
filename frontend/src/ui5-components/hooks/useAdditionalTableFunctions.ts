import { useEffect, useRef, useState } from 'react';
import { calculatePageOffset } from '../services/PageService';
import { PcSortItem, StringDict } from '../models/models';
import _ from 'lodash';

export interface AdditionalTableData {
  forcePage: number | undefined;
  offset: number;
  search: string;
  filter: StringDict;
  sort: PcSortItem | undefined;
  loadData: number;
  onSearch: (val?: string) => void;
  onPageClick: (currentPage?: number) => void;
  onFilter: (accessor: string, filter: string) => void;
  onSort: (e: CustomEvent<{ column: unknown; sortDirection: string }>) => void;
}
export function useAdditionalTableFunctions(
  tableCount: number,
  initialOffset?: number,
  initialSearch?: string,
  initialFilter?: StringDict,
  initialSort?: PcSortItem
): [AdditionalTableData] {
  const [forcePage, setForceState] = useState<number | undefined>(undefined);
  const [offset, setOffset] = useState<number>(initialOffset ?? 0);
  const [search, setSearch] = useState<string>(initialSearch ?? '');
  const [filter, setFilter] = useState<StringDict>(initialFilter ?? {});
  const [sort, setSort] = useState<PcSortItem | undefined>(initialSort ?? undefined);
  const [loadData, setLoadData] = useState<number>(0);

  const isFirstRender = useRef(true);
  useEffect(() => {
    // Components who call useAdditionalTableFunctions() during an onEffect,
    // will use loadData as trigger to load new data.
    // Therefore we have to prevent setting loadData during the first render here,
    // otherwise the Component's onEffect will be called twice
    
    if (isFirstRender.current) { // Do not call during first render
      isFirstRender.current = false; 
      return;
    }
    setLoadData(v => v + 1);
  }, [filter, sort, forcePage, offset, search]);

  function onSearch(val?: string): void {
    setOffset(0);
    setSearch(val ?? '');
    setForceState(0);
  }

  const onPageClick = (currentPage?: number): void => {
    setOffset(calculatePageOffset(currentPage, tableCount));
    setForceState(undefined);
  };

  const onFilter = (accessor: string, filterValue: string): void => {
    if (filter[accessor] !== filterValue) {
      setOffset(0);
      setForceState(0);
      setFilter(f => {
        f[accessor] = filterValue;
        return { ...f };
      });
    }
  };

  const onSort = (e: CustomEvent<{ column: unknown; sortDirection: string }>): void => {
    // @ts-expect-error
    const item: PcSortItem = { id: e.detail.column?.id, sortDirection: e.detail.sortDirection };
    if (!_.isEqual(sort, item)) {
      setOffset(0);
      setForceState(0);
      setSort(s => (item.sortDirection === 'clear' ? undefined : item));
    }
  };

  return [
    { forcePage, offset, search, filter, sort, loadData, onSearch, onPageClick, onFilter, onSort },
  ];
}
