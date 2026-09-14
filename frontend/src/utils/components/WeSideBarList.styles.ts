// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import { addCustomCSS } from '@ui5/webcomponents-base/dist/Theming.js';

/**
 * UI5 pads the inside of a list item by 1rem on the trailing side, which sits
 * between the row content and the list edge and cannot be measured from the
 * outside. The task rows own their trailing spacing (responsive, mirroring the
 * leading side), so the inner padding is dropped — scoped to these rows via the
 * data attribute, every other list keeps the stock spacing.
 */
addCustomCSS(
  'ui5-li',
  `
    :host([data-pc-task-row]) .ui5-li-root {
      padding-inline-end: 0;
    }
  `
).catch(err => {
  console.error(err);
});
