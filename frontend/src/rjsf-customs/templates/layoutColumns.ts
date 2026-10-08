// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export const CAMUNDA_GRID_COLUMNS = 16;

// The Camunda Modeler lays out a row on 16 columns. A field with a width gets exactly that
// many sixteenths of the row, fields without one share the rest; if no field takes the
// rest, an empty track keeps it free. Widths that add up to more than 16 shrink in
// proportion (fr), so the row never overflows.
export const computeGridTemplate = (columns: Array<number | undefined>): string => {
  const widths = columns.map(c => (typeof c === 'number' && c > 0 ? c : undefined));
  const autos = widths.filter(w => w === undefined).length;
  const used = widths.reduce<number>((sum, w) => sum + (w ?? 0), 0);
  const rest = Math.max(CAMUNDA_GRID_COLUMNS - used, 0);
  const tracks = widths.map(w => w ?? rest / autos);
  if (autos === 0 && rest > 0) {
    tracks.push(rest);
  }
  return tracks.map(t => `minmax(0, ${t}fr)`).join(' ');
};
