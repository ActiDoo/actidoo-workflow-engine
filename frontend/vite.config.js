import { defineConfig, loadEnv } from 'vite';
import * as path from 'path';
import react from '@vitejs/plugin-react';

/**
 * Derives the base public path for Vite from an external URL or relative path.
 *
 * Behavior:
 * - Accepts either a full URL (e.g. "https://example.com/app/") or a relative path (e.g. "app" or "/app").
 * - Always ensures the returned base path ends with a trailing slash.
 * - Returns "/" when the input is empty or invalid.
 *
 * Examples:
 *   deriveBaseFromExternalUrl("https://example.com/")      -> "/"
 *   deriveBaseFromExternalUrl("https://example.com/app")   -> "/app/"
 *   deriveBaseFromExternalUrl("/dashboard")                -> "/dashboard/"
 *   deriveBaseFromExternalUrl("dashboard")                 -> "/dashboard/"
 *   deriveBaseFromExternalUrl("")                          -> "/"
 *   deriveBaseFromExternalUrl(null)                        -> "/"
 */
const deriveBaseFromExternalUrl = (value) => {
  if (!value) {
    return '/';
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return '/';
  }

  try {
    // Try to parse as a valid absolute URL
    const url = new URL(trimmed);
    const pathname = url.pathname && url.pathname !== '' ? url.pathname : '/';
    if (pathname === '/') {
      return '/';
    }

    // Ensure pathname ends with a trailing slash
    return pathname.endsWith('/') ? pathname : `${pathname}/`;
  } catch {
    // Fallback for relative paths or invalid URLs
    const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`;
  }
};

const RUNTIME_BASE_PLACEHOLDER = '/__WFE_FRONTEND__/';

const resolveBase = (command, env) => {
  if (command === 'serve') {
    return '/';
  }

  const rawBase = env.VITE_FRONTEND_BASE_URL;
  if (!rawBase) {
    return RUNTIME_BASE_PLACEHOLDER;
  }

  return deriveBaseFromExternalUrl(rawBase);
};

// Main Vite configuration
export default defineConfig(({ command, mode }) => {
  // Load environment variables for the current mode (e.g., development, production)
  const env = loadEnv(mode, __dirname);

  return {
    // Enable React plugin for JSX/TSX support
    plugins: [react()],

    // Compute base path dynamically from environment variable
    base: resolveBase(command, env),

    // Local dev server setup
    server: {
      host: '0.0.0.0',
      port: 3500,
      strictPort: true,
    },

    // Define import alias for shorter import paths
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@/ui5-components': path.resolve(__dirname, 'src/ui5-components'),
      },
    },
  };
});

// # sourceMappingURL=vite.config.js.map
