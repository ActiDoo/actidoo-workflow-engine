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
          exclude: [...configDefaults.exclude, 'src/test/workflows/**'],
        },
      },
      {
        extends: true,
        test: {
          name: 'workflows',
          include: ['src/test/workflows/**/*.test.{ts,tsx}'],
          browser: {
            enabled: true,
            headless: true,
            provider: playwright(),
            instances: [{ browser: 'chromium' }],
          },
        },
      },
    ],
  },
});
