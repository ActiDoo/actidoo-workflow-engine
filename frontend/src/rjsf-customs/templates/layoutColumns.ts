// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export const CAMUNDA_GRID_COLUMNS = 16;
export const BOOTSTRAP_GRID_COLUMNS = 12;

const equalWidthClasses = (count: number): string[] => {
  const className =
    count === 1
      ? 'col-md-12'
      : count === 2
      ? 'col-lg-6'
      : count === 3
      ? 'col-lg-4'
      : count === 4
      ? 'col-lg-3'
      : 'col-lg';
  return Array.from({ length: count }, () => className);
};

const roundHalfToEven = (value: number): number => {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
};

const toBootstrapColumns = (widths16: number[]): number[] => {
  const total16 = widths16.reduce((sum, w) => sum + w, 0);
  const total12 = Math.min(
    BOOTSTRAP_GRID_COLUMNS,
    roundHalfToEven((total16 * BOOTSTRAP_GRID_COLUMNS) / CAMUNDA_GRID_COLUMNS)
  );
  const exact = widths16.map(w => (w * BOOTSTRAP_GRID_COLUMNS) / CAMUNDA_GRID_COLUMNS);
  const result = exact.map(e => Math.max(1, Math.floor(e)));
  let leftover = total12 - result.reduce((sum, w) => sum + w, 0);
  const byRemainder = exact
    .map((e, index) => ({ index, remainder: e - Math.floor(e) }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (const { index } of byRemainder) {
    if (leftover <= 0) break;
    result[index] += 1;
    leftover -= 1;
  }
  return result;
};

export const computeColumnClasses = (columns: Array<number | undefined>): string[] => {
  const explicit = columns.filter((c): c is number => typeof c === 'number' && c > 0);
  if (explicit.length === 0) {
    return equalWidthClasses(columns.length);
  }
  const autoCount = columns.length - explicit.length;
  const remaining16 = CAMUNDA_GRID_COLUMNS - explicit.reduce((sum, c) => sum + c, 0);
  if (autoCount > 0 && remaining16 <= 0) {
    return equalWidthClasses(columns.length);
  }
  const widths16 = columns.map(c =>
    typeof c === 'number' && c > 0 ? Math.min(c, CAMUNDA_GRID_COLUMNS) : remaining16 / autoCount
  );
  return toBootstrapColumns(widths16).map(n => `col-lg-${n}`);
};
