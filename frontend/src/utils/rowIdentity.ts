// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { UI_FIELD_LAYOUT } from '@/models/models';

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
