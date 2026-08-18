// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Standalone on purpose: vite.config.js's notices plugin writes into public/ on serve.

import { defineConfig, configDefaults, coverageConfigDefaults } from 'vitest/config';
import { playwright } from '@vitest/browser-playwright';
import react from '@vitejs/plugin-react';
import * as path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@/ui5-components': path.resolve(__dirname, 'src/ui5-components'),
    },
  },
  test: {
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    env: {
      VITE_FRONTEND_BASE_URL: 'http://localhost/',
      VITE_API_BASE_URL: 'http://localhost/api/',
    },
    server: {
      deps: {
        inline: [/@rjsf\//],
      },
    },
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      exclude: [...coverageConfigDefaults.exclude, 'src/test/**'],
    },
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
          include: ['src/**/*.test.{ts,tsx}'],
          exclude: [...configDefaults.exclude, 'src/test/**'],
        },
      },
      {
        extends: true,
        test: {
          name: 'browser',
          include: ['src/test/**/*.test.{ts,tsx}'],
          setupFiles: ['./src/test/setup.ts', './src/test/setup.browser.ts'],
          // Locator actions and expect.element retry until the test times out; expect.poll
          // (used for non-DOM conditions such as "the fake backend got the call") has its
          // own default.
          testTimeout: 15000,
          expect: { poll: { timeout: 5000 } },
          browser: {
            enabled: true,
            headless: true,
            // Fixed locale so the app's language (navigator.language) does not depend on
            // the machine running the tests.
            provider: playwright({ contextOptions: { locale: 'en-US' } }),
            instances: [{ browser: 'chromium' }],
          },
        },
      },
    ],
  },
});
