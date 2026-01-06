// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

type RuntimeConfig = {
  FRONTEND_BASE_URL?: string;
  API_BASE_URL?: string;
  ENVIRONMENT_LABEL?: string;
};

declare global {
  interface Window {
    __ACTIDOO_RUNTIME_CONFIG__?: RuntimeConfig;
  }
}

const runtimeConfig: RuntimeConfig =
  typeof window !== "undefined" && window.__ACTIDOO_RUNTIME_CONFIG__
    ? window.__ACTIDOO_RUNTIME_CONFIG__
    : {};

const ensureLeadingSlash = (value: string): string =>
  value.startsWith("/") ? value : `/${value}`;

const ensureTrailingSlash = (value: string): string =>
  value.endsWith("/") ? value : `${value}/`;

const sanitisePath = (value: string): string => {
  const trimmed = value.trim();
  if (trimmed === "") {
    return "/";
  }
  return ensureTrailingSlash(ensureLeadingSlash(trimmed));
};

const normaliseBaseUrl = (value: string): string => {
  const trimmed = value.trim();
  if (trimmed === "") {
    return "/";
  }

  try {
    const url = new URL(trimmed);
    const pathname = url.pathname && url.pathname !== "" ? url.pathname : "/";
    const prefix = pathname === "/" ? "/" : ensureTrailingSlash(pathname);
    return `${url.origin}${prefix === "/" ? "/" : prefix}`;
  } catch {
    return sanitisePath(trimmed);
  }
};

const extractUrlPrefix = (value: string): string => {
  try {
    const url = new URL(value);
    const pathname = url.pathname && url.pathname !== "" ? url.pathname : "/";
    return pathname === "/" ? "/" : ensureTrailingSlash(pathname);
  } catch {
    return sanitisePath(value);
  }
};

const getEffectiveConfigValue = (
  runtimeValue: string | undefined,
  envValue: string | undefined,
  label: string
): string => {
  const value = runtimeValue?.trim() || envValue?.trim();

  if (!value) {
    throw new Error(`Missing configuration for ${label}`);
  }

  return value;
};

const getOptionalConfigValue = (
  runtimeValue: string | undefined,
  envValue: string | undefined
): string | undefined => runtimeValue?.trim() || envValue?.trim() || undefined;

// Required: base URL where the frontend is served (Dev = "/", Prod e.g. "https://example.com/wfe/").
const rawFrontendBaseUrl = getEffectiveConfigValue(
  runtimeConfig.FRONTEND_BASE_URL,
  import.meta.env.VITE_FRONTEND_BASE_URL,
  "FRONTEND_BASE_URL"
);
// Absolute base URL incl. trailing slash; used for external links/display.
const frontendBaseUrl = normaliseBaseUrl(rawFrontendBaseUrl);
// Path prefix only ("/" or "/wfe/"); used as router basename and asset prefix.
const urlPrefix = extractUrlPrefix(frontendBaseUrl);

// Required: base URL for BFF/API (e.g. "https://example.com/" or "https://example.com/wfe/").
const rawApiBaseUrl = getEffectiveConfigValue(
  runtimeConfig.API_BASE_URL,
  import.meta.env.VITE_API_BASE_URL,
  "API_BASE_URL"
);
// Normalized API base with trailing slash; apiUrl/apiUrlAdmin/authApiUrl build on top.
const apiBaseUrl = normaliseBaseUrl(rawApiBaseUrl);
// Optional label for the environment (e.g. "DEV", "STG"); shown in the UI.
const environmentLabel = getOptionalConfigValue(
  runtimeConfig.ENVIRONMENT_LABEL,
  import.meta.env.VITE_ENVIRONMENT_LABEL
);

export const environment = {
  apiUrl: `${apiBaseUrl}wfe/bff/`, // BFF endpoint for user routes.
  apiUrlAdmin: `${apiBaseUrl}wfe_admin/bff/`, // BFF endpoint for admin routes.
  authApiUrl: `${apiBaseUrl}auth/`, // Auth endpoints (Keycloak etc.).
  tableCount: import.meta.env.VITE_TABLE_COUNT,
  urlPrefix, // Path prefix for router/assets.
  buildNumber: import.meta.env.VITE_BUILD_NUMBER,
  environmentLabel, // Environment indicator shown in UI.
};
