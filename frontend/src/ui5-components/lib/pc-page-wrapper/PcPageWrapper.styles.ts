// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import { addCustomCSS } from '@ui5/webcomponents-base/dist/Theming.js';

/**
 * UI5's bar shrinks both of its content areas, so a too-wide navigation pushed
 * the right-hand actions out of their own area — they overflow towards the left
 * and drew on top of the menu. The end area keeps its size instead; the header's
 * start content owns the clipping (see PcPageWrapper).
 */
addCustomCSS(
  'ui5-bar',
  `
    .ui5-bar-root .ui5-bar-endcontent-container {
      flex-shrink: 0;
    }
  `
).catch(err => {
  console.error(err);
});
