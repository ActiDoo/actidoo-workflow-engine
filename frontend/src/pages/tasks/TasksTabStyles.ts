// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { addCustomCSS } from '@ui5/webcomponents-base/dist/Theming.js';

addCustomCSS(
  'ui5-tabcontainer',
  `
    :host([data-tasks-tab-container]) .ui5-tab-strip-item {
      opacity: 0.7;
      transform: scale(0.9);
      transform-origin: center bottom;
      transition: transform 0.2s ease, opacity 0.2s ease, color 0.2s ease;
    }

    :host([data-tasks-tab-container]) .ui5-tab-strip-itemText {
      font-size: 0.9rem;
      transition: font-size 0.2s ease, font-weight 0.2s ease;
    }

    :host([data-tasks-tab-container]) .ui5-tab-strip-item--selected {
      color: var(--pc-color-gray-900);
      font-weight: 700;
      opacity: 1;
      transform: scale(1.12);
      z-index: 2;
    }

    :host([data-tasks-tab-container]) .ui5-tab-strip-item--selected .ui5-tab-strip-itemText {
      font-size: 1.1rem;
      font-weight: 700;
    }
  `
).catch(err => {
  console.error(err);
});
