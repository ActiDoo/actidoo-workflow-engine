// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Shared numeric formatting helpers. Used by the currency input widget (edit) and
// by the data-table column builder (display), so currency/number rendering lives
// in one place rather than being re-derived per call site.

/** Format a numeric value with a prepared ``Intl`` formatter; empty for non-numbers. */
export const formatForDisplay = (value: unknown, formatter: Intl.NumberFormat): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '';
  return formatter.format(value);
};

const CURRENCY_PREFIX = 'currency:';

/** Extract the ISO code from a ``currency:<ISO>`` field-schema format hint. */
export const parseCurrencyFormat = (format?: string | null): string | null => {
  if (format?.startsWith(CURRENCY_PREFIX)) {
    const code = format.slice(CURRENCY_PREFIX.length).trim();
    return code || null;
  }
  return null;
};

/**
 * Format a data-table numeric value for display, honoring an optional ``format``
 * hint from the field schema. Supported today: ``currency:<ISO>``. Absent/unknown
 * hints fall back to locale-grouped number formatting. Empty/non-numeric values
 * render as an empty string (the raw string is kept if it isn't a number).
 */
export const formatDataNumber = (
  value: unknown,
  format: string | null | undefined,
  language: string
): string => {
  if (value === null || value === undefined || value === '') return '';
  const num = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(num)) return String(value);
  const currency = parseCurrencyFormat(format);
  if (currency) {
    try {
      return new Intl.NumberFormat(language, { style: 'currency', currency }).format(num);
    } catch {
      // invalid ISO code → fall through to plain number formatting
    }
  }
  return new Intl.NumberFormat(language).format(num);
};
