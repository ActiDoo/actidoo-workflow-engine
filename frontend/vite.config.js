// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { defineConfig, loadEnv } from 'vite';
import * as path from 'path';
import fs from 'fs';
import react from '@vitejs/plugin-react';
import { createRequire } from 'module';

const toPosixPath = (value) => value.split(path.sep).join('/');

const tryGetPackageJsonPathFromModuleId = (rawId) => {
  if (!rawId || rawId.startsWith('\0')) return null;

  const id = rawId.split('?')[0].split('#')[0];
  const normalized = toPosixPath(path.normalize(id));

  const marker = '/node_modules/';
  const idx = normalized.lastIndexOf(marker);
  if (idx < 0) return null;

  const rest = normalized.slice(idx + marker.length);
  if (!rest || rest.startsWith('.vite/')) return null;

  const segments = rest.split('/');
  if (!segments.length) return null;

  const pkgName = segments[0].startsWith('@') ? `${segments[0]}/${segments[1]}` : segments[0];
  if (!pkgName || pkgName.includes('..') || pkgName.includes('\\')) return null;

  const pkgDirPosix = `${normalized.slice(0, idx + marker.length)}${pkgName}`;
  const pkgJsonFsPath = path.normalize(`${pkgDirPosix}/package.json`);
  return fs.existsSync(pkgJsonFsPath) ? pkgJsonFsPath : null;
};

const noticesJsonName = 'third-party-notices.json';
const noticesMdName = 'THIRD_PARTY_NOTICES.md';
const licensesDirName = 'licenses';

const ensureDir = (dirPath) => fs.mkdirSync(dirPath, { recursive: true });

const sanitizePackageName = (packageName) => packageName.replace(/^@/, '').replaceAll('/', '__');

const sanitizePackageId = (name, version) => {
  const safeName = sanitizePackageName(name);
  const safeVersion = String(version || 'UNKNOWN').replaceAll('/', '_');
  return `${safeName}__${safeVersion}`;
};

const normalizeRepositoryUrl = (value) => {
  if (!value) return null;
  let url = String(value).trim();
  if (!url) return null;
  if (url.startsWith('git+')) url = url.slice(4);
  if (url.startsWith('git://')) url = `https://${url.slice('git://'.length)}`;
  return url;
};

const getRepositoryUrl = (modulePkg) => {
  const repositoryRaw =
    typeof modulePkg?.repository === 'string'
      ? modulePkg.repository
      : typeof modulePkg?.repository?.url === 'string'
        ? modulePkg.repository.url
        : null;
  return normalizeRepositoryUrl(repositoryRaw);
};

const toPackageInfo = (modulePkg, moduleDir, fallbackName) => {
  const name = typeof modulePkg?.name === 'string' ? modulePkg.name : fallbackName;
  if (typeof name !== 'string' || !name) return null;

  const version = modulePkg?.version || 'UNKNOWN';
  const license = modulePkg?.license || 'UNKNOWN';
  const repository = getRepositoryUrl(modulePkg);

  return {
    name,
    version,
    license: String(license),
    repository,
    moduleDir,
  };
};

const findLicenseFile = (moduleDir) => {
  const candidates = [
    'LICENSE',
    'LICENSE.md',
    'LICENSE.txt',
    'LICENCE',
    'LICENCE.md',
    'LICENCE.txt',
    'license',
    'license.md',
    'license.txt',
    'COPYING',
    'COPYING.md',
    'COPYING.txt',
  ];

  for (const candidate of candidates) {
    const p = path.join(moduleDir, candidate);
    if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
  }

  return null;
};

const writeNoticesMarkdown = (outDirAbs, rows, { includeBpmnJsWatermarkNotice }) => {
  const outPath = path.join(outDirAbs, noticesMdName);
  const lines = [];

  lines.push('# Third-Party Notices (Frontend)');
  lines.push('');
  lines.push('This build output bundles third-party software. License texts are included in `licenses/`.');
  lines.push('');
  lines.push('## Packages');
  lines.push('');
  lines.push('| Package | Version | Declared license | License text | Upstream |');
  lines.push('|---|---:|---|---|---|');

  for (const row of rows) {
    const link = row.licenseFile ? `licenses/${row.licenseFile}` : '(missing)';
    const upstream = row.repository ? row.repository : '(unknown)';
    lines.push(`| \`${row.name}\` | \`${row.version}\` | \`${row.license}\` | \`${link}\` | \`${upstream}\` |`);
  }

  if (includeBpmnJsWatermarkNotice) {
    lines.push('');
    lines.push('## bpmn-js watermark condition');
    lines.push('');
    lines.push(
      'The `bpmn-js` license includes an additional condition: the bpmn.io project watermark/link shown as part of rendered diagrams MUST NOT be removed or changed and MUST remain visible.',
    );
    lines.push('');
  }

  fs.writeFileSync(outPath, lines.join('\n'), 'utf8');
};

const collectBundledPackageJsonPathsFromRollup = (moduleIds) => {
  const pkgJsonPaths = new Set();
  for (const id of moduleIds) {
    const pkgJsonPath = tryGetPackageJsonPathFromModuleId(id);
    if (pkgJsonPath) pkgJsonPaths.add(pkgJsonPath);
  }
  return Array.from(pkgJsonPaths).sort();
};

const collectTransitiveProdDependencies = (frontendPackageJsonPath) => {
  const pkg = JSON.parse(fs.readFileSync(frontendPackageJsonPath, 'utf8'));
  const roots = Object.keys(pkg.dependencies || {}).sort();
  const rootRequire = createRequire(frontendPackageJsonPath);

  const visitedPackageJsonPaths = new Set();
  const packagesByKey = new Map();
  const queue = roots.map((name) => ({ name, req: rootRequire }));

  while (queue.length) {
    const { name, req } = queue.shift();

    let pkgJsonPath;
    try {
      pkgJsonPath = req.resolve(`${name}/package.json`);
    } catch {
      continue;
    }

    if (visitedPackageJsonPaths.has(pkgJsonPath)) continue;
    visitedPackageJsonPaths.add(pkgJsonPath);

    let modulePkg;
    try {
      modulePkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8'));
    } catch {
      continue;
    }

    const moduleDir = path.dirname(pkgJsonPath);
    const pkgInfo = toPackageInfo(modulePkg, moduleDir, name);
    if (!pkgInfo) continue;

    const packageKey = `${pkgInfo.name}@${pkgInfo.version}`;
    if (!packagesByKey.has(packageKey)) packagesByKey.set(packageKey, pkgInfo);

    const childRequire = createRequire(pkgJsonPath);
    const deps = Object.keys(modulePkg.dependencies || {});
    const optional = Object.keys(modulePkg.optionalDependencies || {});
    for (const depName of [...deps, ...optional]) {
      queue.push({ name: depName, req: childRequire });
    }
  }

  return Array.from(packagesByKey.values()).sort((a, b) => {
    const nameCmp = a.name.localeCompare(b.name);
    if (nameCmp !== 0) return nameCmp;
    return String(a.version).localeCompare(String(b.version));
  });
};

const collectPackagesFromPackageJsonPaths = (packageJsonPaths) => {
  const packagesByKey = new Map();

  for (const pkgJsonPath of packageJsonPaths) {
    let modulePkg;
    try {
      modulePkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8'));
    } catch {
      continue;
    }

    const moduleDir = path.dirname(pkgJsonPath);
    const pkgInfo = toPackageInfo(modulePkg, moduleDir, null);
    if (!pkgInfo) continue;

    const packageKey = `${pkgInfo.name}@${pkgInfo.version}`;
    if (!packagesByKey.has(packageKey)) packagesByKey.set(packageKey, pkgInfo);
  }

  return Array.from(packagesByKey.values()).sort((a, b) => {
    const nameCmp = a.name.localeCompare(b.name);
    if (nameCmp !== 0) return nameCmp;
    return String(a.version).localeCompare(String(b.version));
  });
};

const writeThirdPartyNotices = (outDirAbs, packages, { clean, alsoCopyToPrefixDirAbs }) => {
  const licensesDirAbs = path.join(outDirAbs, licensesDirName);

  ensureDir(outDirAbs);

  if (clean) {
    fs.rmSync(licensesDirAbs, { recursive: true, force: true });
    fs.rmSync(path.join(outDirAbs, noticesMdName), { force: true });
    fs.rmSync(path.join(outDirAbs, noticesJsonName), { force: true });
  }
  ensureDir(licensesDirAbs);

  const rows = [];
  let copied = 0;
  const generatedAt = new Date().toISOString();
  const bpmnJsWatermarkNotice =
    'The bpmn-js license includes an additional condition: the bpmn.io project watermark/link shown as part of rendered diagrams MUST NOT be removed or changed and MUST remain visible.';

  for (const entry of packages) {
    const { name, version, license, repository, moduleDir } = entry;

    const licensePath = findLicenseFile(moduleDir);
    let licenseFileName = null;
    if (licensePath) {
      const ext = path.extname(licensePath) || '.txt';
      licenseFileName = `${sanitizePackageId(name, version)}${ext}`;
      fs.copyFileSync(licensePath, path.join(licensesDirAbs, licenseFileName));
      copied += 1;
    } else {
      console.warn(`WARN: no LICENSE file found for ${name} in ${moduleDir} (declared license: ${license})`);
    }

    rows.push({ name, version, license: String(license), licenseFile: licenseFileName, repository });
  }

  const bpmnJsIncluded = rows.some((r) => r.name === 'bpmn-js');
  if (bpmnJsIncluded) {
    const bpmnJs = rows.find((r) => r.name === 'bpmn-js');
    if (!bpmnJs || !bpmnJs.licenseFile) {
      throw new Error(`Expected bpmn-js LICENSE to be copied into ${licensesDirAbs}.`);
    }
  }

  writeNoticesMarkdown(outDirAbs, rows, { includeBpmnJsWatermarkNotice: bpmnJsIncluded });
  fs.writeFileSync(
    path.join(outDirAbs, noticesJsonName),
    JSON.stringify(
      {
        generatedAt,
        dependencies: rows,
        bpmnJsIncluded,
        bpmnJsWatermarkNotice,
        rawNoticesPath: noticesMdName,
      },
      null,
      2,
    ),
    'utf8',
  );

  if (alsoCopyToPrefixDirAbs) {
    ensureDir(alsoCopyToPrefixDirAbs);
    if (clean) {
      fs.rmSync(path.join(alsoCopyToPrefixDirAbs, licensesDirName), { recursive: true, force: true });
      fs.rmSync(path.join(alsoCopyToPrefixDirAbs, noticesMdName), { force: true });
      fs.rmSync(path.join(alsoCopyToPrefixDirAbs, noticesJsonName), { force: true });
    }

    fs.copyFileSync(path.join(outDirAbs, noticesMdName), path.join(alsoCopyToPrefixDirAbs, noticesMdName));
    fs.copyFileSync(path.join(outDirAbs, noticesJsonName), path.join(alsoCopyToPrefixDirAbs, noticesJsonName));
    fs.cpSync(path.join(outDirAbs, licensesDirName), path.join(alsoCopyToPrefixDirAbs, licensesDirName), {
      recursive: true,
    });
  }

  console.log(`Wrote ${copied} license texts for ${rows.length} dependencies to ${licensesDirAbs}`);
};

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

const thirdPartyNoticesPlugin = ({ command, env }) => {
  const rootDir = __dirname;
  const packageJsonPath = path.join(rootDir, 'package.json');

  const prefix = env?.VITE_FRONTEND_BASE_URL ? deriveBaseFromExternalUrl(env.VITE_FRONTEND_BASE_URL) : '/';
  const devPrefix = prefix === '/' ? null : prefix;

  return {
    name: 'actidoo-third-party-notices',
    apply: () => true,
    configureServer(server) {
      if (command !== 'serve') return;
      if (!server.config.publicDir) return;

      const publicDirAbs = path.isAbsolute(server.config.publicDir)
        ? server.config.publicDir
        : path.resolve(server.config.root, server.config.publicDir);

      const packages = collectTransitiveProdDependencies(packageJsonPath);

      const prefixDirAbs =
        devPrefix && devPrefix !== '/'
          ? path.join(publicDirAbs, devPrefix.replace(/^\/+/, '').replace(/\/+$/, ''))
          : null;

      writeThirdPartyNotices(publicDirAbs, packages, { clean: true, alsoCopyToPrefixDirAbs: prefixDirAbs });
    },
    generateBundle(outputOptions) {
      if (command !== 'build') return;

      const outDirRaw = outputOptions.dir || null;
      if (!outDirRaw) return;
      const outDirAbs = path.isAbsolute(outDirRaw) ? outDirRaw : path.resolve(rootDir, outDirRaw);

      const bundledPackageJsonPaths = collectBundledPackageJsonPathsFromRollup(this.getModuleIds());
      const packages = bundledPackageJsonPaths.length
        ? collectPackagesFromPackageJsonPaths(bundledPackageJsonPaths)
        : collectTransitiveProdDependencies(packageJsonPath);

      writeThirdPartyNotices(outDirAbs, packages, { clean: true, alsoCopyToPrefixDirAbs: null });
    },
  };
};

// Main Vite configuration
export default defineConfig(({ command, mode }) => {
  // Load environment variables for the current mode (e.g., development, production)
  const env = loadEnv(mode, __dirname);

  return {
    // Enable React plugin for JSX/TSX support
    plugins: [react(), thirdPartyNoticesPlugin({ command, env })],

    // Compute base path dynamically from environment variable
    base: resolveBase(command, env),

    // Reduce noisy Sass deprecation warnings from dependencies (e.g. Bootstrap).
    css: {
      preprocessorOptions: {
        scss: {
          quietDeps: true,
        },
      },
    },

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
