// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import {
  AnalyticalTableColumnDefinition,
  Button,
  ButtonDesign,
  Icon,
  InputType,
  Option,
  Select,
  TextAlign,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/resize-horizontal';
import { PcDateColumn, PcInputColumn, PcTableData } from '@/ui5-components';
import { PcArrowLink } from '@/ui5-components/utils/PcArrowLink';
import { DataActionSchema, DataFieldSchema } from '@/models/dataViewer';
import { type useTranslation } from '@/i18n';
import { FormatFieldCtx, formatFieldValue } from '@/pages/data/formatFieldValue';

type Translate = ReturnType<typeof useTranslation>['t'];

interface ColumnContext {
  modelName: string;
  onAction: (row: Record<string, unknown>, action: DataActionSchema) => void;
  // ID column display: compact (8 chars + ellipsis) by default, toggleable to the
  // full value via the icon in the column header (for copying/searching).
  showFullIds: boolean;
  onToggleIdDisplay: () => void;
}

const booleanFilter = (
  tableData: PcTableData,
  columnId: string,
  t: Translate
): React.ReactElement => (
  <Select
    className="w-full"
    onChange={e => {
      tableData.onFilter(columnId, e.detail.selectedOption?.dataset?.value ?? '');
    }}>
    <Option data-value="">{t('data.filter.all')}</Option>
    <Option data-value="true">{t('data.yes')}</Option>
    <Option data-value="false">{t('data.no')}</Option>
  </Select>
);

// Render a cell value through the shared formatter, deriving the per-version
// download context (id/version) from the row.
const cell = (field: DataFieldSchema, modelName: string, language: string, t: Translate) => (
  instance: any
): React.ReactNode => {
  const row = instance.row.original;
  const ctx: FormatFieldCtx = { modelName, language, t, recordId: row.id, version: row.version };
  return <>{formatFieldValue(field, row[field.name], ctx)}</>;
};

const fieldColumn = (
  field: DataFieldSchema,
  tableData: PcTableData,
  t: Translate,
  ctx: ColumnContext,
  language: string
): AnalyticalTableColumnDefinition => {
  const { modelName } = ctx;
  const common = {
    disableSortBy: !field.sortable,
    disableFilters: !field.filterable,
  };

  // Compact id column: a full UUID has no scan value — show a monospaced short
  // form with a trailing ellipsis; the icon in the header switches to the full,
  // copyable value. (Only string PKs — the numeric ``version`` PK part stays a
  // plain number column.)
  if (field.primary_key && (field.type === 'string' || !field.type)) {
    const base = PcInputColumn(field.name, field.label, tableData);
    const full = ctx.showFullIds;
    return {
      ...base,
      ...common,
      width: full ? 330 : 130,
      Header: (data: any) => (
        <div className="flex items-center justify-between w-full min-w-0 gap-1">
          <span className="truncate">
            {typeof base.Header === 'function' ? (base.Header as any)(data) : <>{field.label}</>}
          </span>
          <span
            className="flex items-center shrink-0 cursor-pointer"
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation(); // don't trigger the column's sort/filter popover
              ctx.onToggleIdDisplay();
            }}>
            <Icon
              name="resize-horizontal"
              accessibleName={t(full ? 'data.shortenIds' : 'data.showFullIds')}
              showTooltip
              className="w-4 h-4 text-brand-primary hover:text-brand-primary-strong"
            />
          </span>
        </div>
      ),
      Cell: (instance: any) => {
        const value = String(instance.row.original[field.name] ?? '');
        const truncated = !full && value.length > 8;
        return (
          <span className="font-mono" title={value}>
            {truncated ? `${value.slice(0, 8)}…` : value}
          </span>
        );
      },
    };
  }

  switch (field.type) {
    case 'datetime':
      // Cell override: PcDateColumn's default cell formats without a locale —
      // route the value through the shared, locale-aware formatter instead.
      // Filter and sortType from the spread stay intact.
      return {
        ...PcDateColumn(field.name, field.label, tableData),
        ...common,
        minWidth: 170,
        Cell: cell(field, modelName, language, t),
      };
    case 'date':
      return {
        ...PcDateColumn(field.name, field.label, tableData),
        ...common,
        minWidth: 130,
        Cell: cell(field, modelName, language, t),
      };
    case 'number':
    case 'decimal':
      // Honor the field-schema ``format`` hint (e.g. ``currency:EUR``) for display,
      // while the underlying value stays numeric for server-side sort/filter.
      return {
        ...PcInputColumn(field.name, field.label, tableData, InputType.Number),
        ...common,
        minWidth: 120,
        hAlign: TextAlign.End,
        Cell: cell(field, modelName, language, t),
      };
    case 'boolean':
      return {
        ...PcInputColumn(field.name, field.label, tableData),
        ...common,
        minWidth: 110,
        hAlign: TextAlign.Center,
        Cell: cell(field, modelName, language, t),
        Filter: field.filterable ? (d: any) => booleanFilter(tableData, d.column.id, t) : undefined,
      };
    case 'file':
      return {
        ...PcInputColumn(field.name, field.label, tableData),
        ...common,
        minWidth: 180,
        Cell: cell(field, modelName, language, t),
      };
    default:
      return { ...PcInputColumn(field.name, field.label, tableData), ...common, minWidth: 150 };
  }
};

const actionsColumn = (
  t: Translate,
  ctx: ColumnContext,
  width: number
): AnalyticalTableColumnDefinition => ({
  accessor: '__actions',
  Header: () => <>{t('data.actions')}</>,
  disableFilters: true,
  disableSortBy: true,
  width,
  Cell: (instance: any) => {
    const row = instance.row.original;
    const actions = (row.__actions ?? []) as DataActionSchema[];
    if (actions.length === 0) return null;
    return (
      <div className="flex flex-wrap gap-2">
        {actions.map(action => (
          <Button
            key={action.key}
            design={ButtonDesign.Transparent}
            onClick={() => {
              ctx.onAction(row, action);
            }}>
            {action.label}
          </Button>
        ))}
      </div>
    );
  },
});

// Trailing arrow opening the record's detail/version page.
const detailColumn = (modelName: string): AnalyticalTableColumnDefinition => ({
  accessor: '__detail',
  Header: () => null,
  disableFilters: true,
  disableSortBy: true,
  width: 60,
  hAlign: TextAlign.Center,
  Cell: (instance: any) => (
    <PcArrowLink link={`/data/${encodeURIComponent(modelName)}/${String(instance.row.original.id)}`} />
  ),
});

export const buildDataColumns = (
  fields: DataFieldSchema[],
  tableData: PcTableData,
  t: Translate,
  language: string,
  ctx: ColumnContext,
  hasActions: boolean,
  actionsWidth = 220
): AnalyticalTableColumnDefinition[] => {
  const columns = fields.map(field => fieldColumn(field, tableData, t, ctx, language));
  if (hasActions) columns.push(actionsColumn(t, ctx, actionsWidth));
  columns.push(detailColumn(ctx.modelName));
  return columns;
};
