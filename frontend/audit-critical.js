#!/usr/bin/env node

/**
 * audit-critical.js
 * * Führt `yarn npm audit` aus, filtert nach kritischen Lücken (High/Critical),
 * reichert die Daten via OSV.dev API an (CVEs, Fixes) und berechnet 
 * Upgrade-Pfade für transitive Abhängigkeiten.
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const https = require('https'); // Native Node.js HTTPS module

const rootDir = __dirname;
const MIN_SEVERITY = 'high';

const severityLevels = {
  info: 0, low: 1, moderate: 2, high: 3, critical: 4,
};

// Root package + dependency info
let rootPkgName = null;
let rootDeps = {};

try {
  const pkgRaw = fs.readFileSync(path.join(rootDir, 'package.json'), 'utf8');
  const pkg = JSON.parse(pkgRaw);
  rootPkgName = pkg.name || null;
  rootDeps = {
    ...(pkg.dependencies || {}),
    ...(pkg.devDependencies || {}),
    ...(pkg.optionalDependencies || {}),
    ...(pkg.peerDependencies || {})
  };
} catch (e) {
  rootPkgName = null;
  rootDeps = {};
}

const npmListCache = new Map();

// --- HELPER FUNCTIONS ---

function cleanVersion(raw) {
  if (!raw) return '0.0.0';
  const str = String(raw);
  const match = str.match(/(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)/);
  return match ? match[1] : '0.0.0';
}

function parseSemVer(version) {
  const cleaned = cleanVersion(version);
  const match = cleaned.match(/^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$/);
  if (!match) return { major: 0, minor: 0, patch: 0, prerelease: '', original: version };
  return {
    major: parseInt(match[1], 10),
    minor: parseInt(match[2], 10),
    patch: parseInt(match[3], 10),
    prerelease: match[4] || '',
    original: cleaned
  };
}

function compareSemVer(v1, v2) {
  const a = parseSemVer(v1);
  const b = parseSemVer(v2);
  if (a.major !== b.major) return a.major > b.major ? 1 : -1;
  if (a.minor !== b.minor) return a.minor > b.minor ? 1 : -1;
  if (a.patch !== b.patch) return a.patch > b.patch ? 1 : -1;
  if (a.prerelease === '' && b.prerelease !== '') return 1;
  if (a.prerelease !== '' && b.prerelease === '') return -1;
  if (a.prerelease !== '' && b.prerelease !== '') return a.prerelease > b.prerelease ? 1 : -1;
  return 0;
}

function runCommand(cmd, args) {
  return spawnSync(cmd, args, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
    maxBuffer: 50 * 1024 * 1024,
    cwd: rootDir
  });
}

/**
 * Fetcht Details von der OSV.dev API anhand der GHSA-ID.
 * Nutzt natives https Modul, um keine dependencies zu brauchen.
 */
function fetchOsvDetails(rawId) {
  return new Promise((resolve) => {
    // 1. Falls undefined/null -> Abbruch
    if (!rawId) {
      resolve(null);
      return;
    }

    // 2. Sicherstellen, dass es ein String ist (falls es eine Number ist)
    const ghsaId = String(rawId);

    // 3. Prüfen, ob es eine GHSA ID ist
    if (!ghsaId.startsWith('GHSA')) {
      resolve(null);
      return;
    }

    const url = `https://api.osv.dev/v1/vulns/${ghsaId}`;
    
    https.get(url, (res) => {
      if (res.statusCode !== 200) {
        resolve(null);
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(null);
        }
      });
    }).on('error', () => {
      resolve(null);
    });
  });
}

function npmListPackage(pkgName) {
  if (npmListCache.has(pkgName)) return npmListCache.get(pkgName);

  try {
    const res = runCommand('npm', ['ls', pkgName, '--all', '--json']);
    if (!res.stdout) {
      npmListCache.set(pkgName, null);
      return null;
    }

    const json = JSON.parse(res.stdout);
    const paths = [];

    function dfs(node, pathSoFar) {
      if (!node) return;
      const name = node.name || '(root)';
      const version = node.version || null;
      const nextPath = [...pathSoFar, { name, version }];

      if (name === pkgName) {
        paths.push(nextPath);
      }

      if (node.dependencies) {
        for (const [childName, childNode] of Object.entries(node.dependencies)) {
          dfs({ name: childName, version: childNode.version, dependencies: childNode.dependencies }, nextPath);
        }
      }
    }

    dfs({ name: json.name || '(root)', version: json.version, dependencies: json.dependencies }, []);

    if (paths.length === 0) {
      if (json.dependencies && json.dependencies[pkgName] && json.dependencies[pkgName].version) {
        const v = json.dependencies[pkgName].version;
        const fallbackPath = [
          { name: json.name || '(root)', version: json.version },
          { name: pkgName, version: v }
        ];
        const info = { version: v, path: fallbackPath };
        npmListCache.set(pkgName, info);
        return info;
      }
      npmListCache.set(pkgName, null);
      return null;
    }

    paths.sort((a, b) => a.length - b.length);
    const best = paths[0];
    const last = best[best.length - 1];
    const info = { version: last.version || null, path: best };
    npmListCache.set(pkgName, info);
    return info;
  } catch (e) {
    npmListCache.set(pkgName, null);
    return null;
  }
}

function getLocalVersion(pkgName) {
  const info = npmListPackage(pkgName);
  if (info && info.version) return cleanVersion(info.version);

  try {
    const res = runCommand('npm', ['view', pkgName, 'version', '--json']);
    if (res.status === 0 && res.stdout) {
      let out = JSON.parse(res.stdout);
      if (Array.isArray(out)) out = out.pop();
      return cleanVersion(out);
    }
  } catch (e) {}

  return '0.0.0';
}

function getPackageVersions(packageName) {
  try {
    const res = runCommand('npm', ['view', packageName, 'versions', '--json']);
    if (res.status === 0 && res.stdout) {
      const output = JSON.parse(res.stdout);
      return Array.isArray(output) ? output : [output];
    }
  } catch (e) {}
  return [];
}

function checkParentDependency(parentName, parentVersion, childName) {
  try {
    const res = runCommand('npm', ['view', `${parentName}@${parentVersion}`, 'dependencies', '--json']);
    if (res.status === 0 && res.stdout) {
      const deps = JSON.parse(res.stdout);
      return deps[childName] || null;
    }
  } catch (e) {}
  return null;
}

function resolveMaxSatisfying(pkgName, range) {
  try {
    const res = runCommand('npm', ['view', `${pkgName}@${range}`, 'version', '--json']);
    if (res.status === 0 && res.stdout) {
      let out = JSON.parse(res.stdout);
      if (Array.isArray(out)) out = out.pop();
      return out;
    }
  } catch (e) {}
  return null;
}

function findParentFix(parentPkg, childPkg, currentParentVer, neededChildVer) {
  const allParentVersions = getPackageVersions(parentPkg);
  const currentParsed = parseSemVer(currentParentVer);

  const candidates = allParentVersions.filter(v => {
    const p = parseSemVer(v);
    if (compareSemVer(v, currentParentVer) < 0) return false;
    if (currentParsed.prerelease === '' && p.prerelease !== '') return false;
    return true;
  });

  if (candidates.length === 0) return null;
  candidates.sort(compareSemVer);

  const toCheck = new Set(candidates.slice(0, 8));
  const seenMap = {};
  candidates.forEach(v => {
    const parts = cleanVersion(v).split('.');
    seenMap[`${parts[0]}.${parts[1]}`] = v;
  });
  Object.values(seenMap).forEach(v => toCheck.add(v));
  const sortedChecks = Array.from(toCheck).sort(compareSemVer);

  // console.log(`   🔎 Checking ${sortedChecks.length} candidates for ${parentPkg} (Starting from ${currentParentVer})...`);

  for (const pVer of sortedChecks) {
    const childRange = checkParentDependency(parentPkg, pVer, childPkg);
    if (!childRange) return { parentVer: pVer, childVer: 'Removed', isFixed: true };

    const resolvedChildVer = resolveMaxSatisfying(childPkg, childRange);
    if (resolvedChildVer && compareSemVer(resolvedChildVer, neededChildVer) >= 0) {
      return { parentVer: pVer, childVer: resolvedChildVer, isFixed: true };
    }
  }
  return null;
}

function formatPath(pathNodes) {
  if (!pathNodes || pathNodes.length === 0) return '';
  return pathNodes
    .map(n => (n.version ? `${n.name}@${n.version}` : n.name))
    .join(' > ');
}

function findDeclaredAncestor(pathNodes) {
  if (!pathNodes || pathNodes.length < 2) return null;
  for (let i = 1; i < pathNodes.length; i++) {
    const name = pathNodes[i].name;
    if (rootDeps && Object.prototype.hasOwnProperty.call(rootDeps, name)) {
      return {
        index: i,
        name,
        range: rootDeps[name]
      };
    }
  }
  return null;
}

function buildUpgradeChain(pathNodes, startIndex, neededChildVer) {
  const segments = [];
  let currentNeeded = neededChildVer;

  for (let i = pathNodes.length - 2; i >= startIndex; i--) {
    const parentNode = pathNodes[i];
    const childNode = pathNodes[i + 1];

    const parentName = parentNode.name;
    const childName = childNode.name;
    const currentParentVer = parentNode.version
      ? cleanVersion(parentNode.version)
      : getLocalVersion(parentName);

    const fix = findParentFix(parentName, childName, currentParentVer, currentNeeded);
    if (!fix || !fix.isFixed) {
      return {
        ok: false,
        failingParent: parentName,
        failingChild: childName,
        neededChildVer: currentNeeded,
        segments
      };
    }

    segments.unshift({
      parentName,
      from: currentParentVer,
      to: fix.parentVer,
      viaChild: childName,
      viaChildTo: fix.childVer
    });

    currentNeeded = fix.parentVer;
  }

  return {
    ok: true,
    segments,
    rootRequiredVer: currentNeeded
  };
}

function extractPkgName(locator) {
  if (!locator) return null;
  const lastAt = locator.lastIndexOf('@');
  if (lastAt > 0) {
    return locator.substring(0, lastAt);
  }
  return locator;
}

// --- AUDIT RUNNER ---

function runAudit() {
  const env = { ...process.env };
  env.YARN_NPM_REGISTRY_SERVER = env.YARN_NPM_REGISTRY_SERVER || env.NPM_CONFIG_REGISTRY || 'https://registry.npmjs.org';

  console.log('Running yarn npm audit...');
  const result = spawnSync('yarn', ['npm', 'audit', '--recursive', '--json'], {
    cwd: rootDir,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    env,
    maxBuffer: 50 * 1024 * 1024
  });

  if (result.status !== 0 && !result.stdout) {
    if (result.stderr) console.error(result.stderr);
    process.exit(result.status || 1);
  }
  return result.stdout.trim();
}

function parseAuditOutput(stdout) {
  if (!stdout) return [];
  const advisories = [];
  const lines = stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);

  lines.forEach(line => {
    try {
      const entry = JSON.parse(line);

      // FORMAT A: Yarn Berry Tree Format
      if (entry.value && entry.children && entry.children.Severity) {
        
        let parentName = null;
        if (entry.children.Dependents) {
          const deps = entry.children.Dependents;
          if (typeof deps === 'string') {
            parentName = extractPkgName(deps);
          } else if (Array.isArray(deps) && deps.length > 0) {
            parentName = extractPkgName(deps[0]?.value || deps[0]);
          }
        }

        let cves = [];
        if (entry.children.CVE) {
          cves = Array.isArray(entry.children.CVE) ? entry.children.CVE : [String(entry.children.CVE)];
        }
        // Fallback ID für späteres Matching, aber nicht direkt in CVEs pushen
        // um Duplikate zu vermeiden, wenn die API die ID auch zurückgibt.
        
        // Patched Version Suche
        let patchedVer = entry.children['Patched Versions'] || '';
        if (!patchedVer && entry.children.Recommendation) {
          const recMatch = String(entry.children.Recommendation).match(/version\s+(\d+\.\d+\.\d+)/i);
          if (recMatch) patchedVer = recMatch[1];
        }

        advisories.push({
          module_name: entry.value,
          severity: String(entry.children.Severity || '').toLowerCase(),
          title: entry.children.Issue,
          url: entry.children.URL,
          id: entry.children.ID, // GHSA-xxxx ID oder numerisch
          cves: cves,
          vulnerable_versions: entry.children['Vulnerable Versions'],
          patched_versions: patchedVer,
          recommendation: entry.children.Recommendation || '',
          parent_module: parentName,
          findings: [{ version: 'Unknown', paths: [] }]
        });
      }
      // FORMAT B: Standard npm audit JSON
      else if (entry.type === 'auditAdvisory' && entry.data?.advisory) {
        const adv = entry.data.advisory;
        adv.cves = adv.cves || [];
        adv.id = adv.github_advisory_id || adv.id;
        advisories.push(adv);
      }
      else if (entry.advisories) {
        Object.values(entry.advisories).forEach(a => {
            a.cves = a.cves || [];
            a.id = a.github_advisory_id || a.id;
            advisories.push(a);
        });
      }
    } catch (e) {}
  });

  return advisories;
}

// --- MAIN LOGIC (ASYNC) ---

async function main() {
  const stdout = runAudit();
  const advisories = parseAuditOutput(stdout);

  const minLevel = severityLevels[MIN_SEVERITY];
  const criticals = advisories.filter(a => {
    const sev = String(a.severity || '').toLowerCase();
    return severityLevels[sev] >= minLevel;
  });

  if (criticals.length === 0) {
    console.log(`✅ No critical vulnerabilities found. (Parsed ${advisories.length} total advisories)`);
    return;
  }

  console.log(`\n🚨 [ALARM] Found ${criticals.length} critical vulnerabilities:\n`);

  // Loop mit await für API Calls
  for (let index = 0; index < criticals.length; index++) {
    const advisory = criticals[index];

    // --- API ENRICHMENT ---
    
    // 1. Versuche GHSA ID zu finden
    let ghsaId = null;
    if (advisory.id && String(advisory.id).startsWith('GHSA')) {
        ghsaId = advisory.id;
    }
    
    // 2. Fallback: Suche in der URL, wenn ID numerisch oder leer
    if (!ghsaId && advisory.url) {
        const match = advisory.url.match(/(GHSA-[a-zA-Z0-9-]+)/);
        if (match) {
            ghsaId = match[1];
        }
    }

    if (ghsaId) {
        // console.log(`   ... fetching details for ${ghsaId}`);
        const osvData = await fetchOsvDetails(ghsaId);
        if (osvData) {
            // A. CVEs mergen
            if (osvData.aliases) {
                osvData.aliases.forEach(alias => {
                    if (alias.startsWith('CVE') && !advisory.cves.includes(alias)) {
                        advisory.cves.push(alias);
                    }
                });
            }
            
            // B. Fix Version finden (OSV: affected[].ranges[].events[])
            if (osvData.affected) {
                for (const aff of osvData.affected) {
                    // Matching Package Name
                    const isSamePackage = !aff.package || (aff.package.name === advisory.module_name);
                    
                    if (isSamePackage && aff.ranges) {
                        for (const range of aff.ranges) {
                            if (range.events) {
                                for (const evt of range.events) {
                                    if (evt.fixed) {
                                        // Erste gefundene Fix-Version übernehmen, falls noch keine da ist
                                        if (!advisory.patched_versions) {
                                            advisory.patched_versions = evt.fixed;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    // ---------------------

    const npmInfo = npmListPackage(advisory.module_name);
    const pathNodes = npmInfo && npmInfo.path && npmInfo.path.length ? npmInfo.path : null;

    let installedVulnerableVersion = 'Unknown';
    if (advisory.findings && advisory.findings[0] && advisory.findings[0].version && advisory.findings[0].version !== 'Unknown') {
      installedVulnerableVersion = advisory.findings[0].version;
    } else if (npmInfo && npmInfo.version) {
      installedVulnerableVersion = npmInfo.version;
    }

    const isDirectRootDep = !!rootDeps[advisory.module_name];
    const declaredAncestor = pathNodes ? findDeclaredAncestor(pathNodes) : null;

    let neededPatchVer = null;
    // Priorität: API/JSON > Recommendation Text > Vulnerable Regex
    if (advisory.patched_versions) {
      const match = String(advisory.patched_versions).match(/(\d+\.\d+\.\d+)/);
      if (match) neededPatchVer = match[1];
    }
    if (!neededPatchVer && advisory.recommendation) {
       const match = String(advisory.recommendation).match(/version\s+(\d+\.\d+\.\d+)/i);
       if (match) neededPatchVer = match[1];
    }
    if (!neededPatchVer && advisory.vulnerable_versions) {
      const match = String(advisory.vulnerable_versions).match(/<\s*(\d+\.\d+\.\d+)/);
      if (match) neededPatchVer = match[1];
    }

    console.log(`--- Issue #${index + 1} ---`);
    console.log(`📦 Vulnerable Lib:      ${advisory.module_name}`);
    
    // ID Anzeige:
    const displayId = ghsaId || advisory.id || 'N/A';
    const cveString = (advisory.cves && advisory.cves.length > 0) ? advisory.cves.join(', ') : displayId;
    console.log(`🛡️  CVE / ID:           ${cveString}`);
    
    if (advisory.url) {
      console.log(`🌐 Mehr Infos:          ${advisory.url}`);
    }

    console.log(`❌ Installed (Lib):     ${installedVulnerableVersion !== 'Unknown' ? installedVulnerableVersion : '(See yarn.lock)'}`);

    if (pathNodes) {
      console.log(`🧬 Dependency-Pfad:     ${formatPath(pathNodes)}`);
    }

    if (isDirectRootDep) {
      const currentDirect = npmInfo && npmInfo.version ? cleanVersion(npmInfo.version) : getLocalVersion(advisory.module_name);
      console.log(`ℹ️  Direkt-Dependency:   ${advisory.module_name}`);
      console.log(`ℹ️  Aktuell installiert: ${currentDirect}`);
    } else if (declaredAncestor) {
      const ancestorNode = pathNodes[declaredAncestor.index];
      const currentAncestorVer = ancestorNode && ancestorNode.version
        ? cleanVersion(ancestorNode.version)
        : getLocalVersion(declaredAncestor.name);
      console.log(`🔗 Eingetragene Dep.:    ${declaredAncestor.name} (Deklariert als: ${declaredAncestor.range})`);
      console.log(`ℹ️  Aktuell installiert: ${currentAncestorVer}`);
    } else if (advisory.parent_module) {
      const currentParentVer = getLocalVersion(advisory.parent_module);
      console.log(`🔗 Via Parent (Heuristik): ${advisory.parent_module}`);
      console.log(`ℹ️  Parent Current:      ${currentParentVer}`);
    }

    console.log(`\n🛠️  Action Plan:`);

    if (!neededPatchVer) {
      console.log(`   Konnte Zielversion für Fix nicht automatisch bestimmen (auch nicht via API).`);
      console.log(`   👉 Empfehlung: Prüfe Advisory manuell und führe z.B. 'yarn up ${advisory.module_name}' aus.`);
      console.log('');
      continue; 
    }

    // Fall 1: Direct Dependency
    if (isDirectRootDep) {
      const currentDirect = npmInfo && npmInfo.version ? cleanVersion(npmInfo.version) : getLocalVersion(advisory.module_name);
      const allVers = getPackageVersions(advisory.module_name);
      const candidates = allVers.filter(v => {
        if (compareSemVer(v, currentDirect) < 0) return false;
        return compareSemVer(v, neededPatchVer) >= 0;
      });
      candidates.sort(compareSemVer);

      if (candidates.length > 0) {
        const target = candidates[0];
        console.log(`   Direktes Update der eingetragenen Dependency:`);
        console.log(`   Von: ${currentDirect}`);
        console.log(`   Auf (minimal sicher): ${target}`);
        console.log(`\n   👉 Command: yarn up ${advisory.module_name}@${target}`);
      } else {
        console.log(`   Keine passende Version für ${advisory.module_name} gefunden, die >= ${neededPatchVer} ist.`);
      }
      console.log('');
      continue;
    }

    // Fall 2: Transitive Dependency mit Pfad
    if (pathNodes && declaredAncestor) {
      const chainResult = buildUpgradeChain(pathNodes, declaredAncestor.index, neededPatchVer);
      const ancestorNode = pathNodes[declaredAncestor.index];
      const currentAncestorVer = ancestorNode && ancestorNode.version
        ? cleanVersion(ancestorNode.version)
        : getLocalVersion(declaredAncestor.name);

      if (chainResult.ok) {
        const rootSegment = chainResult.segments[0] || null;
        const targetAncestorVer = rootSegment ? rootSegment.to : currentAncestorVer;

        if (compareSemVer(targetAncestorVer, currentAncestorVer) > 0) {
          console.log(`   ✅ Fix-Kette berechnet.`);
          console.log(`   Eingetragene Dependency: ${declaredAncestor.name}`);
          console.log(`   Von: ${currentAncestorVer}`);
          console.log(`   Auf (minimal sicher): ${targetAncestorVer}`);
          console.log(`\n   👉 Command: yarn up ${declaredAncestor.name}@${targetAncestorVer}`);
        } else {
          console.log(`   Die aktuell deklarierte Version ${declaredAncestor.name}@${currentAncestorVer} kann bereits eine sichere Unter-Dependency auflösen.`);
          console.log(`\n   👉 Command (Lockfile aktualisieren): yarn up ${declaredAncestor.name}`);
          console.log(`      Falls nötig zusätzlich: yarn up -R ${advisory.module_name}`);
        }
        console.log('');
        continue;
      } else {
        console.log(`   ❌ Konnte keinen durchgängigen Fix bis zur eingetragenen Dependency berechnen.`);
        console.log(`   Letzter Schritt ohne Lösung: ${chainResult.failingParent} -> ${chainResult.failingChild} (braucht mind. ${chainResult.neededChildVer})`);
        console.log(`   👉 Empfehlung: Arbeite mit 'resolutions' in package.json oder fixe ${chainResult.failingParent} manuell.`);
        console.log('');
        continue;
      }
    }

    // Fall 3: Fallback (Direct Update der Parent-Dep ohne Pfad)
    const directDepName = advisory.parent_module || advisory.module_name;
    const currentParentVersion = getLocalVersion(directDepName);

    if (directDepName === advisory.module_name) {
        const allVers = getPackageVersions(directDepName);
        const candidates = allVers.filter(v => {
            if (compareSemVer(v, currentParentVersion) < 0) return false;
            return compareSemVer(v, neededPatchVer) >= 0;
        });
        candidates.sort(compareSemVer);

        if (candidates.length > 0) {
            const target = candidates[0];
            console.log(`   Direct Update (Fallback):`);
            console.log(`   👉 Command: yarn up ${directDepName}@${target}`);
        } else {
            console.log(`   Keine Version für ${directDepName} gefunden, die >= ${neededPatchVer} ist.`);
        }
    } else {
      const fix = findParentFix(directDepName, advisory.module_name, currentParentVersion, neededPatchVer);
      if (fix && fix.isFixed) {
        if (fix.parentVer !== currentParentVersion) {
          console.log(`   ✅ Fix via Parent (Fallback):`);
          console.log(`   Update Parent: ${directDepName}`);
          console.log(`   Von: ${currentParentVersion}`);
          console.log(`   Auf: ${fix.parentVer}`);
          console.log(`\n   👉 Command: yarn up ${directDepName}@${fix.parentVer}`);
        } else {
          console.log(`   Parent-Version ${currentParentVersion} kann bereits eine sichere Unter-Dependency nutzen.`);
          console.log(`\n   👉 Command (Refresh): yarn up ${directDepName}`);
          console.log(`      (Sub-Dep forcieren: yarn up -R ${advisory.module_name})`);
        }
      } else {
        console.log(`   ❌ Kein automatischer Parent-Fix gefunden (Fallback).`);
        console.log(`   👉 Empfehlung: Arbeite mit 'resolutions' in package.json.`);
      }
    }
    console.log('');
  }

  process.exitCode = 1;
}

main();