// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Two extra locators next to Vitest's built-in ones (getByRole, getByText, ...):
// - getById: rjsf gives every form field a stable id ("root_<key>", "root_<list>_<i>_<key>").
// - getByCss: escape hatch for controls inside a web component's shadow root that carry no
//   role, label or text (the native file input of ui5-file-uploader). Do not use it for
//   anything a user could address by role, label or text.
// Like all Vitest locators these look through shadow DOM and retry until the test times out.

import { locators, type Locator } from 'vitest/browser';

declare module '@vitest/browser/context' {
  interface LocatorSelectors {
    getById: (id: string) => Locator;
    getByCss: (css: string) => Locator;
  }
}

locators.extend({
  getById(id: string) {
    return `id=${id}`;
  },
  getByCss(css: string) {
    return `css=${css}`;
  },
});
