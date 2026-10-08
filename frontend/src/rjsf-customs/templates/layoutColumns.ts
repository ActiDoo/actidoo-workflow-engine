// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export const CAMUNDA_GRID_COLUMNS = 16;

// The Camunda Modeler lays out a row on 16 columns. A field with a width gets exactly that
// many sixteenths (pc-col-<n> in TaskForm.scss); fields without one share the rest of the
// row (pc-col).
export const computeColumnClasses = (columns: Array<number | undefined>): string[] =>
  columns.map(c =>
    typeof c === 'number' && c > 0 ? `pc-col-${Math.min(c, CAMUNDA_GRID_COLUMNS)}` : 'pc-col'
  );
