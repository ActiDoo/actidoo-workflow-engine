import React, { useEffect } from 'react';
import '@/ui5-components/lib/pc-analytical-table/PcAnalysticalTable.scss';
import {
  AnalyticalTable,
  AnalyticalTablePropTypes,
  Icon,
  Loader,
  MessageStrip,
  MessageStripDesign,
  Text,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/nav-back';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';
import ReactPaginate from 'react-paginate';
import { PcSortItem, StringDict } from '@/ui5-components/models/models';
import { queryParamToAccessor } from '@/ui5-components/services/PageService';

export interface PhAnalyticalTableProps extends AnalyticalTablePropTypes {
  response?: number;
  itemsCount?: number;
  pageChange?: (page?: number) => void;
  initialPage?: number;
  limit?: number;
  forcePage?: number;
  sort?: PcSortItem;
  filter?: StringDict;
}

export const PcAnalyticalTable: React.FC<PhAnalyticalTableProps> = props => {
  const {
    response,
    itemsCount,
    pageChange,
    initialPage,
    limit = 20,
    forcePage,
    sort,
    filter,
    ...tableData
  } = props;

  const handlePageClick = (selectedItem: { selected: number }): void => {
    if (pageChange) pageChange(selectedItem.selected);
  };

  useEffect(() => {
    if (sort) {
      // @ts-expect-error
      tableRef.current?.setSortBy([
        { id: queryParamToAccessor(sort.id), desc: sort.sortDirection === 'desc' },
      ]);
    }
  }, [tableData.data]);

  const pageCount = itemsCount ? Math.ceil(itemsCount / limit) : 10;
  const hasPagination = pageChange && itemsCount;
  const tableClasses = hasPagination ? 'pc-analytical-table' : '';

  const message =
    response && response !== 200 ? (
      <MessageStrip className="mb-8" design={MessageStripDesign.Negative} hideCloseButton={true}>
        An error has occurred while loading the table data. Reload the page to try again.
      </MessageStrip>
    ) : null;
  const tableRef = React.useRef(null);

  return (
    <div className="mt-[-4px]">
      {message}
      <Loader className={`${tableData.loading ? '' : 'opacity-0'}`} />
      <div className="relative">
        <AnalyticalTable
          {...tableData}
          loading={tableData.data.length ? false : tableData.loading}
          className={tableClasses}
          visibleRows={limit}
          minRows={1}
          tableInstance={tableRef}
        />
        {tableData.loading ? <div className="bg-white/50 absolute inset-0" /> : null}
      </div>
      {hasPagination ? (
        <div className="flex items-center justify-between h-16">
          <Text>Items: {itemsCount}</Text>
          {pageCount > 1 ? (
            <ReactPaginate
              className="pc-pagination"
              breakLabel="..."
              nextLabel={<Icon name="navigation-right-arrow" className="w-6 h-full " />}
              onPageChange={p => {
                handlePageClick(p);
              }}
              pageRangeDisplayed={2}
              initialPage={initialPage}
              marginPagesDisplayed={2}
              pageCount={pageCount}
              previousLabel={<Icon name="nav-back" className="w-6 h-full " />}
              forcePage={forcePage}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
};
