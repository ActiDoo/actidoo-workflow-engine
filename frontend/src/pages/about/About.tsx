// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';

import { PcPage } from '@/ui5-components';
import { useTranslation } from '@/i18n';
import { environment } from '@/environment';

type ThirdPartyDependency = {
  name: string;
  version: string;
  license: string;
  licenseFile: string | null;
  repository?: string | null;
};

type ThirdPartyNotices = {
  generatedAt: string;
  dependencies: ThirdPartyDependency[];
  bpmnJsIncluded?: boolean;
  bpmnJsWatermarkNotice: string;
  rawNoticesPath: string;
};

const About: React.FC = () => {
  const { t } = useTranslation();
  const [notices, setNotices] = useState<ThirdPartyNotices | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assetBaseUrl, setAssetBaseUrl] = useState<string>(import.meta.env.BASE_URL);

  const candidates = [environment.urlPrefix, import.meta.env.BASE_URL, '/'].filter(Boolean);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        let json: ThirdPartyNotices | null = null;
        let baseUsed: string | null = null;

        for (const candidate of candidates) {
          const base = candidate.endsWith('/') ? candidate : `${candidate}/`;
          const res = await fetch(`${base}third-party-notices.json`, { cache: 'no-cache' });
          if (res.ok) {
            json = (await res.json()) as ThirdPartyNotices;
            baseUsed = base;
            break;
          }
        }
        if (!json || !baseUsed) {
          throw new Error('third-party-notices.json not found');
        }
        if (!cancelled) {
          setNotices(json);
          setAssetBaseUrl(baseUsed);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setNotices(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <PcPage header={{ title: t('about.title') }}>
      <div className="max-w-5xl">
        <div className="text-sm text-pc-gray-700">
          <div>{t('about.description')}</div>
          <div className="mt-2">
            <a
              className="no-underline text-pc-gray-700 hover:text-pc-gray-900"
              href={`${assetBaseUrl}${notices?.rawNoticesPath ?? 'THIRD_PARTY_NOTICES.md'}`}
              target="_blank"
              rel="noreferrer">
              {t('about.openRawNotices')}
            </a>
          </div>
        </div>

        {notices ? (
          <>
            <div className="mt-6">
              <div className="text-sm font-semibold">{t('about.thirdPartyTitle')}</div>
              <div className="text-xs text-pc-gray-600 mt-1">
                {t('about.generatedAt', { value: notices.generatedAt })}
              </div>
            </div>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left border-b border-pc-gray-200">
                    <th className="py-2 pr-4">{t('about.table.package')}</th>
                    <th className="py-2 pr-4">{t('about.table.version')}</th>
                    <th className="py-2 pr-4">{t('about.table.license')}</th>
                    <th className="py-2">{t('about.table.text')}</th>
                  </tr>
                </thead>
                <tbody>
                  {notices.dependencies.map(dep => (
                    <tr key={`${dep.name}@${dep.version}`} className="border-b border-pc-gray-100">
                      <td className="py-2 pr-4 font-mono">{dep.name}</td>
                      <td className="py-2 pr-4 font-mono">{dep.version}</td>
                      <td className="py-2 pr-4 font-mono">{dep.license}</td>
                      <td className="py-2">
                        {dep.licenseFile ? (
                          <a
                            className="no-underline text-pc-gray-700 hover:text-pc-gray-900 font-mono"
                            href={`${assetBaseUrl}licenses/${dep.licenseFile}`}
                            target="_blank"
                            rel="noreferrer">
                            {t('about.view')}
                          </a>
                        ) : dep.repository ? (
                          <a
                            className="no-underline text-pc-gray-700 hover:text-pc-gray-900 font-mono"
                            href={dep.repository}
                            target="_blank"
                            rel="noreferrer">
                            {t('about.upstream')}
                          </a>
                        ) : (
                          <span className="text-pc-gray-500">{t('about.missing')}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {(notices.bpmnJsIncluded ?? notices.dependencies.some(dep => dep.name === 'bpmn-js')) ? (
              <div className="mt-6">
                <div className="text-sm font-semibold">{t('about.bpmnJsWatermarkTitle')}</div>
                <div className="text-sm text-pc-gray-700 mt-1">{notices.bpmnJsWatermarkNotice}</div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="mt-6 text-sm text-pc-gray-700">
            {t('about.noticesUnavailable')}
            {error ? <div className="text-xs text-pc-gray-500 mt-1">{error}</div> : null}
          </div>
        )}
      </div>
    </PcPage>
  );
};

export default About;
