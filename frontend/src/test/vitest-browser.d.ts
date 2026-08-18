// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// tsconfig resolves modules with "node", which does not read package "exports" maps and
// therefore cannot find "vitest/browser" (a virtual module Vitest provides at runtime).
// This maps its types onto the file that ships them; runtime resolution is Vitest's.
declare module 'vitest/browser' {
  export * from '@vitest/browser/context';
}
