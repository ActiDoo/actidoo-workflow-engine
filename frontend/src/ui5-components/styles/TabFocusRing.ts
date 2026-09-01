// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import { addCustomCSS } from '@ui5/webcomponents-base/dist/Theming.js';

/**
 * UI5 draws the focus ring of a tab on plain `:focus`, so clicking a tab leaves a
 * brand-colored box around it until the focus moves on. Suppress it for pointer
 * focus only — keyboard users keep the ring through `:focus-visible`.
 *
 * `!important` because the library's own rules carry higher specificity, and the
 * ring is a `::before` pseudo element inside the tab container's shadow root.
 */
addCustomCSS(
  'ui5-tabcontainer',
  `
    .ui5-tab-strip-item:focus:not(:focus-visible) .ui5-tab-strip-itemText::before,
    .ui5-tab-strip-item:focus:not(:focus-visible) .ui5-tab-strip-itemContent::before,
    .ui5-tab-strip-item:focus:not(:focus-visible) .ui5-tab-strip-item-icon-outer::before {
      border: none !important;
    }
  `
).catch(err => {
  console.error(err);
});
