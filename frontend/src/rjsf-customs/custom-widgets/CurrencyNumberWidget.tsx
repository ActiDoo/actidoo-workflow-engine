// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Storage contract — stable, do not break:
//   - props.value is a JSON number (or undefined for empty); never a formatted string.
//   - props.onChange(value) is called with the parsed number or undefined.
//   - The currency symbol comes from props.uiSchema and is purely a display hint;
//     it is NOT persisted with the value.
//   - parseInput accepts both DE ("1.234,56") and EN ("1,234.56" / "1234.56") inputs,
//     so changing the display locale later does not invalidate user habits or values
//     that were entered under a previous locale.

import { WidgetProps } from '@rjsf/utils';
import { ChangeEvent, FocusEvent, ReactElement, useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/i18n';

const formatForDisplay = (value: unknown, formatter: Intl.NumberFormat): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '';
  return formatter.format(value);
};

// Detect the locale's decimal separator. Falls back to "." if Intl gives us
// something exotic we don't understand.
const localeDecimalSeparator = (locale: string): ',' | '.' => {
  const sample = (1.1).toLocaleString(locale);
  return sample.charAt(1) === ',' ? ',' : '.';
};

// parseInput is locale-aware but stays *tolerant* — users sometimes paste or
// type values in the opposite locale's notation, and we want to do the right
// thing rather than silently turn 12,34 € into 1234 €.
//
// Rules per locale (decSep = locale decimal, thouSep = the other one):
//   "1234"              → 1234                 (no separator)
//   "1<thouSep>234<decSep>56" → 1234.56        (canonical)
//   "1<decSep>234<thouSep>56" → 1234.56        (opposite-locale notation)
//   "1234<decSep>56"    → 1234.56              (just decimal)
//   "1234<thouSep>56"   → 1234.56              (opposite-locale decimal — heuristic)
//   "1<thouSep>234"     → 1234                 (locale's thousands grouping)
//   "1<thouSep>50"      → 1.50                 (not 3 digits after — opposite-locale decimal)
const parseInput = (raw: string, locale: string): number | undefined => {
  const trimmed = raw.trim();
  if (trimmed === '') return undefined;

  const decSep = localeDecimalSeparator(locale);
  const thouSep = decSep === ',' ? '.' : ',';
  const lastDec = trimmed.lastIndexOf(decSep);
  const lastThou = trimmed.lastIndexOf(thouSep);

  let normalized: string;
  if (lastDec >= 0 && lastThou >= 0) {
    // Both separators present — the later one is the decimal.
    if (lastDec > lastThou) {
      normalized = trimmed.split(thouSep).join('').replace(decSep, '.');
    } else {
      normalized = trimmed.split(decSep).join('').replace(thouSep, '.');
    }
  } else if (lastDec >= 0) {
    // Only the locale's decimal separator → trust the user.
    normalized = trimmed.replace(decSep, '.');
  } else if (lastThou >= 0) {
    // Only the locale's thousands separator. Ambiguous:
    //   - "1.234" in DE could be 1234 (DE thousands) or 1.234 (EN decimal pasted in)
    //   - "1,234" in EN could be 1234 (EN thousands) or 1.234 (typo)
    // Heuristic: groups of exactly 3 digits → thousands; everything else → opposite-locale decimal.
    const parts = trimmed.split(thouSep);
    const fractional = parts[parts.length - 1];
    if (parts.length > 2 || (parts.length === 2 && fractional.length === 3)) {
      normalized = parts.join('');
    } else {
      normalized = trimmed.replace(thouSep, '.');
    }
  } else {
    normalized = trimmed;
  }

  const num = Number(normalized);
  return Number.isNaN(num) ? undefined : num;
};

const CurrencyNumberWidget = (props: WidgetProps): ReactElement => {
  const { language } = useTranslation();

  const displayFormatter = useMemo(
    () =>
      new Intl.NumberFormat(language, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    [language]
  );

  const editFormatter = useMemo(
    () =>
      new Intl.NumberFormat(language, {
        useGrouping: false,
        maximumFractionDigits: 20,
      }),
    [language]
  );

  const symbol =
    (props.uiSchema?.['ui:currency'] as string | undefined) ??
    (props.uiSchema?.['ui:suffixAdorner'] as string | undefined) ??
    '';

  const [isFocused, setIsFocused] = useState(false);
  const [draft, setDraft] = useState<string>(formatForDisplay(props.value, displayFormatter));

  useEffect(() => {
    if (!isFocused) setDraft(formatForDisplay(props.value, displayFormatter));
  }, [props.value, isFocused, displayFormatter]);

  const onFocus = (_evt: FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    if (props.value === undefined || props.value === null || props.value === '') {
      setDraft('');
    } else {
      // While editing, show the value with the current locale's decimal separator.
      // parseInput is locale-tolerant, so this is purely UX, not a contract.
      setDraft(editFormatter.format(Number(props.value)));
    }
  };

  const handleInput = (evt: ChangeEvent<HTMLInputElement>) => {
    setDraft(evt.target.value);
  };

  const onBlur = (_evt: FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    const parsed = parseInput(draft, language);
    props.onChange(parsed);
    setDraft(formatForDisplay(parsed, displayFormatter));
  };

  return (
    <div className="mb-0">
      {props.label && (
        <label className={'text-sm ' + (props.disabled ? 'opacity-75' : '')}>
          {props.required ? props.label + '*' : props.label}
        </label>
      )}

      <div className="flex items-center">
        <input
          className="form-control"
          type="text"
          inputMode="decimal"
          value={draft}
          onFocus={onFocus}
          onChange={handleInput}
          onBlur={onBlur}
          required={props.required}
          disabled={props.disabled}
          readOnly={props.readonly}
        />
        {symbol && (
          <span className="ml-2 text-sm" aria-hidden="true">
            {symbol}
          </span>
        )}
      </div>

      {props.options.description ? (
        <p className={'text-gray-500 text-xs ' + (props.disabled ? 'opacity-80' : '')}>
          {props.options.description}
        </p>
      ) : null}
    </div>
  );
};

export default CurrencyNumberWidget;
