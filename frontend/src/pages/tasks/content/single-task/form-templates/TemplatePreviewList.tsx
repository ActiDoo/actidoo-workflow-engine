// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';

import { useTranslation } from '@/i18n';
import { SkippedTemplateField } from '@/models/models';

interface TemplatePreviewListProps {
  jsonschema?: Record<string, any>;
  applicableData: Record<string, unknown>;
  skippedFields: SkippedTemplateField[];
  savedHint?: string;
  skippedHint?: string;
}

const isAttachmentObject = (value: unknown): boolean =>
  !!value &&
  typeof value === 'object' &&
  !Array.isArray(value) &&
  ('filename' in value || 'datauri' in value);

const attachmentCount = (value: unknown): number | null => {
  if (isAttachmentObject(value)) return 1;
  if (Array.isArray(value) && value.length > 0 && value.every(isAttachmentObject))
    return value.length;
  return null;
};

const TemplatePreviewList: React.FC<TemplatePreviewListProps> = ({
  jsonschema,
  applicableData,
  skippedFields,
  savedHint,
  skippedHint,
}) => {
  const { t } = useTranslation();
  const properties = jsonschema?.properties ?? {};

  const formatScalar = (value: unknown): string => {
    if (typeof value === 'boolean') return value ? t('common.labels.yes') : t('common.labels.no');
    if (value === null || value === undefined || value === '') {
      return t('formTemplates.preview.emptyValue');
    }
    return String(value);
  };

  const resolveOption = (
    oneOf: Array<{ const?: unknown; title?: string }>,
    value: unknown
  ): string => {
    const match = oneOf.find(option => option.const === value);
    return match?.title ?? formatScalar(value);
  };

  // Leaf value: file count for attachments, option label for static selects/radios, else the raw value.
  const formatFieldValue = (node: Record<string, any> | undefined, value: unknown): string => {
    const files = attachmentCount(value);
    if (files !== null) {
      return files === 1
        ? t('formTemplates.preview.fileSingular', { count: files })
        : t('formTemplates.preview.filePlural', { count: files });
    }
    if (Array.isArray(node?.oneOf)) {
      if (value === null || value === undefined || value === '') return formatScalar(value);
      return resolveOption(node.oneOf, value);
    }
    if (node?.type === 'array' && Array.isArray(node.items?.oneOf) && Array.isArray(value)) {
      return value.map(item => resolveOption(node.items.oneOf, item)).join(', ');
    }
    if (Array.isArray(value)) return value.map(item => formatScalar(item)).join(', ');
    if (value && typeof value === 'object') return '';
    return formatScalar(value);
  };

  const nodeForKey = (key: string): Record<string, any> | undefined => {
    let currentProps: Record<string, any> = properties;
    let node: Record<string, any> | undefined;
    for (const segment of key.split('.')) {
      node = currentProps?.[segment];
      if (!node) return undefined;
      if (node.type === 'object' && node.properties) currentProps = node.properties;
      else if (node.type === 'array' && node.items?.properties)
        currentProps = node.items.properties;
      else currentProps = {};
    }
    return node;
  };

  const renderContent = (node: Record<string, any>, value: unknown): React.ReactNode => {
    if (
      node.type === 'object' &&
      node.properties &&
      value &&
      typeof value === 'object' &&
      !Array.isArray(value)
    ) {
      return renderTable(node.properties, value as Record<string, unknown>);
    }
    if (node.type === 'array' && node.items?.properties && Array.isArray(value)) {
      return (
        <div className="flex flex-col gap-2">
          {(value as Array<Record<string, unknown>>).map((item, index) => (
            <div key={index}>
              <div className="text-xs text-neutral-400">#{index + 1}</div>
              {renderTable(node.items.properties, item)}
            </div>
          ))}
        </div>
      );
    }
    return formatFieldValue(node, value);
  };

  const renderTable = (
    props: Record<string, any>,
    data: Record<string, unknown>
  ): React.ReactNode => (
    <table className="text-sm">
      <tbody>
        {Object.entries(data).map(([key, value]) => {
          const node = props[key] ?? {};
          return (
            <tr key={key} className="align-top">
              <td className="pr-3 py-0.5 align-top">
                <span className="text-neutral-500 whitespace-nowrap">{node.title ?? key}:</span>
              </td>
              <td className="w-full py-0.5">{renderContent(node, value)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        {savedHint ? (
          <span className="text-xs font-semibold text-neutral-500">{savedHint}</span>
        ) : null}
        {Object.keys(applicableData).length > 0 ? (
          renderTable(properties, applicableData)
        ) : (
          <span className="text-sm text-neutral-500">{t('formTemplates.preview.emptyValue')}</span>
        )}
      </div>

      {skippedFields.length > 0 ? (
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-neutral-500">
            {skippedHint ?? t('formTemplates.preview.skippedHint')}
          </span>
          <table className="text-sm">
            <tbody>
              {skippedFields.map(field => (
                <tr key={field.key} className="align-top">
                  <td className="pr-3 py-0.5 align-top">
                    <span className="text-neutral-400 whitespace-nowrap">{field.label}:</span>
                  </td>
                  <td className="w-full py-0.5">
                    <span className="text-neutral-400 line-through">
                      {formatFieldValue(nodeForKey(field.key), field.value)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
};

export default TemplatePreviewList;
