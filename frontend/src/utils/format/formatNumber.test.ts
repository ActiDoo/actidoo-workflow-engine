// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { formatForDisplay, parseCurrencyFormat, formatDataNumber } from './formatNumber';

describe('parseCurrencyFormat', () => {
  it('extracts the ISO code from a currency format hint', () => {
    expect(parseCurrencyFormat('currency:EUR')).toBe('EUR');
    expect(parseCurrencyFormat('currency: USD ')).toBe('USD');
  });

  it('returns null for an empty code', () => {
    expect(parseCurrencyFormat('currency:')).toBe(null);
    expect(parseCurrencyFormat('currency:   ')).toBe(null);
  });

  it('returns null for missing or unrelated formats', () => {
    expect(parseCurrencyFormat(undefined)).toBe(null);
    expect(parseCurrencyFormat(null)).toBe(null);
    expect(parseCurrencyFormat('date-time')).toBe(null);
  });
});

describe('formatDataNumber', () => {
  it('formats currency values for the given locale', () => {
    const result = formatDataNumber(1234.5, 'currency:EUR', 'de-DE');
    expect(result).toContain('€');
    expect(result).toContain('1.234,50');
  });

  it('renders empty values as empty string', () => {
    expect(formatDataNumber(null, null, 'de-DE')).toBe('');
    expect(formatDataNumber(undefined, null, 'de-DE')).toBe('');
    expect(formatDataNumber('', null, 'de-DE')).toBe('');
  });

  it('keeps non-numeric strings unchanged', () => {
    expect(formatDataNumber('n/a', null, 'de-DE')).toBe('n/a');
  });

  it('coerces numeric strings', () => {
    expect(formatDataNumber('1234.5', null, 'de-DE')).toBe('1.234,5');
  });

  it('falls back to plain number formatting on invalid ISO codes', () => {
    expect(formatDataNumber(10, 'currency:NOPE', 'de-DE')).toBe('10');
  });
});

describe('formatForDisplay', () => {
  const formatter = new Intl.NumberFormat('de-DE');

  it('formats numbers with the given formatter', () => {
    expect(formatForDisplay(1234.5, formatter)).toBe('1.234,5');
  });

  it('returns empty string for non-numbers and NaN', () => {
    expect(formatForDisplay(NaN, formatter)).toBe('');
    expect(formatForDisplay('12', formatter)).toBe('');
    expect(formatForDisplay(undefined, formatter)).toBe('');
  });
});
