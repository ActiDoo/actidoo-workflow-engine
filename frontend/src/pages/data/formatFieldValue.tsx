// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { Icon } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/download';
import { environment } from '@/environment';
import { DataFieldSchema, DataFileRef } from '@/models/dataViewer';
import { type useTranslation } from '@/i18n';
import { formatDataNumber } from '@/utils/format/formatNumber';

type Translate = ReturnType<typeof useTranslation>['t'];

// Attachments are addressed per record version: /{model}/{id}/versions/{version}/attachments/{hash}.
export const attachmentUrl = (
  modelName: string,
  recordId: unknown,
  version: unknown,
  hash?: string | null
): string =>
  `${environment.apiUrl}user/workflow-data/${encodeURIComponent(modelName)}/${String(
    recordId
  )}/versions/${String(version)}/attachments/${String(hash)}`;

export interface FormatFieldCtx {
  modelName: string;
  language: string;
  t: Translate;
  recordId: unknown;
  version: unknown;
}

const renderFileRefs = (refs: DataFileRef[], ctx: FormatFieldCtx): React.ReactNode => {
  if (!Array.isArray(refs) || refs.length === 0) return null;
  return (
    <div className="flex flex-col">
      {refs.map((ref, idx) => (
        // A real anchor: keyboard-focusable, announced as a link, and middle-click/
        // "open in new tab" work — unlike a span with window.open.
        <a
          key={`${ref.hash ?? idx}`}
          href={attachmentUrl(ctx.modelName, ctx.recordId, ctx.version, ref.hash)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand-primary underline inline-flex items-center gap-1">
          <Icon name="download" className="w-4 h-4" />
          {ref.filename ?? ref.hash}
        </a>
      ))}
    </div>
  );
};

/**
 * Render a single field value the same way in the table and on the detail page.
 * Type-driven: currency/number via the format hint, localized date/datetime,
 * boolean as yes/no, file as per-version download links, everything else as text.
 */
export const formatFieldValue = (
  field: DataFieldSchema,
  value: unknown,
  ctx: FormatFieldCtx
): React.ReactNode => {
  switch (field.type) {
    case 'number':
    case 'decimal':
      return formatDataNumber(value, field.format, ctx.language);
    case 'date':
      return value ? new Date(String(value)).toLocaleDateString(ctx.language) : null;
    case 'datetime':
      return value ? new Date(String(value)).toLocaleString(ctx.language) : null;
    case 'boolean':
      if (value === null || value === undefined) return null;
      return value ? ctx.t('data.yes') : ctx.t('data.no');
    case 'file':
      return renderFileRefs((value ?? []) as DataFileRef[], ctx);
    default:
      return value === null || value === undefined ? null : String(value);
  }
};
