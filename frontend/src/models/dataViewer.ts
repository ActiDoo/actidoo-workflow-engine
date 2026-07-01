// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Types mirroring the backend workflow-data API (DataModelSchema / ListRowsResponse).

export type DataDisplayType =
  | 'string'
  | 'number'
  | 'decimal'
  | 'boolean'
  | 'datetime'
  | 'date'
  | 'file';

export interface DataFileRef {
  id?: string | null;
  hash?: string | null;
  filename?: string | null;
  mimetype?: string | null;
}

export interface DataFieldSchema {
  name: string;
  label: string;
  type: DataDisplayType;
  format?: string | null;
  nullable: boolean;
  primary_key: boolean;
  virtual: boolean;
  sortable: boolean;
  filterable: boolean;
}

export interface DataActionSchema {
  key: string;
  label: string;
  target: string;
}

export interface DataModelSchema {
  name: string;
  // Human-readable model label (falls back to ``name`` when not declared).
  label?: string | null;
  fields: DataFieldSchema[];
  // Number of rows the current user may see. Only set in the catalog (list_models).
  row_count?: number | null;
  // Whether the model declares follow-up actions — stable per model.
  has_actions?: boolean | null;
}

// A workflow that uses a data model and that the current user may start
// (the "involved processes" picker on the data-model detail page).
export interface DataProcessRef {
  name: string;
  title: string;
}

export interface DataRow {
  data: Record<string, unknown>;
  actions: DataActionSchema[];
}

export interface DataRowsResponse {
  ITEMS: DataRow[];
  COUNT: number;
  model: DataModelSchema;
}

// One version of a record on the detail page (data + metadata independent of the
// declared fields).
export interface DataVersionEntry {
  data: Record<string, unknown>;
  created_at: string | null;
  action: string | null;
}

export interface DataVersionChainResponse {
  versions: DataVersionEntry[];
  model: DataModelSchema;
  // Follow-up workflows available on the current (head) version for this user.
  actions: DataActionSchema[];
}
