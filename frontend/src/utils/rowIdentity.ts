// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { ROW_ID_KEY, UI_FIELD_LAYOUT } from '@/models/models';

// Dynamic-list row identity (ADR 010), frontend side. Mirrors the backend
// helpers in wf/service_form.py (section "Dynamic-list row identity"):
// dynamic lists are recognized by their items uischema, and the technical
// row id lives in the form data only - never in a schema.

export const isDynamicListUiItems = (uiItems: unknown): boolean =>
  typeof uiItems === 'object' &&
  uiItems !== null &&
  (uiItems as Record<string, unknown>)['ui:field'] === UI_FIELD_LAYOUT;

export const generateRowId = (): string => {
  if (typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // crypto.randomUUID only exists in secure contexts (and Safari >= 15.4);
  // plain-http deployments fall back to RFC-4122 v4 via getRandomValues.
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
};

type Row = Record<string, any>;

const isRow = (value: unknown): value is Row =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const rowIdOf = (row: unknown): string | undefined => {
  const id = isRow(row) ? row[ROW_ID_KEY] : undefined;
  return typeof id === 'string' && id !== '' ? id : undefined;
};

/**
 * Give the rows of a locally stored draft the identity the server has for them.
 *
 * The server stamps every row it hands out, so a draft written before that
 * happened carries ids the server never issued. Submitting those would make the
 * backend take every row for a new one and drop the values it owns. A draft that
 * knows at least one stored id is current - ids it does not share are rows the
 * user added, and those keep theirs.
 *
 * Positions are all a draft has to go by, so rows are matched by index. Runs once
 * when the draft is loaded, never while editing.
 */
export const adoptServerRowIds = (
  uiSchema: unknown,
  data: unknown,
  serverData: unknown
): { data: unknown; changed: boolean } => {
  let changed = false;

  const walk = (ui: unknown, node: unknown, serverNode: unknown): unknown => {
    if (!isRow(ui) || !isRow(node)) return node;

    let result = node;
    const replace = (key: string, value: unknown) => {
      result = result === node ? { ...node } : result;
      result[key] = value;
      changed = true;
    };

    for (const [key, entry] of Object.entries(ui)) {
      if (key.startsWith('ui:') || !isRow(entry)) continue;

      const value = result[key];
      const serverValue = isRow(serverNode) ? serverNode[key] : undefined;

      if (!isDynamicListUiItems(entry.items)) {
        const walked = walk(entry, value, serverValue);
        if (walked !== value) replace(key, walked);
        continue;
      }

      if (!Array.isArray(value)) continue;
      const serverRows: unknown[] = Array.isArray(serverValue) ? serverValue : [];
      const serverIds = new Set(serverRows.map(rowIdOf).filter((id): id is string => !!id));
      const knowsStoredRows = value.some(row => {
        const id = rowIdOf(row);
        return !!id && serverIds.has(id);
      });
      const adoptByIndex = serverIds.size > 0 && !knowsStoredRows;

      let rowsChanged = false;
      const rows = value.map((row, index) => {
        if (!isRow(row)) return row;
        const serverRow = adoptByIndex
          ? serverRows[index]
          : serverRows.find(candidate => rowIdOf(candidate) === rowIdOf(row));

        let current = row;
        const serverRowId = rowIdOf(serverRow);
        if (adoptByIndex && serverRowId && rowIdOf(row) !== serverRowId) {
          current = { ...row, [ROW_ID_KEY]: serverRowId };
          rowsChanged = true;
        }

        const walked = walk(entry.items, current, serverRow);
        if (walked !== current) rowsChanged = true;
        return walked;
      });

      if (rowsChanged) replace(key, rows);
    }

    return result;
  };

  return { data: walk(uiSchema, data, serverData), changed };
};
