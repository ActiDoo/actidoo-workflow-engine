// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';

import Markdown from 'markdown-to-jsx';

import { environment } from '@/environment';
import { useTranslation } from '@/i18n';

const DEFAULT_LANGUAGE = 'en';

const buildCandidatePaths = (language: string): string[] => {
  const bases = [environment.urlPrefix, import.meta.env.BASE_URL, '/'].filter(Boolean);
  const languages = Array.from(new Set([language, DEFAULT_LANGUAGE]));
  const paths: string[] = [];
  for (const lang of languages) {
    for (const candidate of bases) {
      const base = candidate.endsWith('/') ? candidate : `${candidate}/`;
      paths.push(`${base}branding/help.${lang}.md`);
    }
  }
  return paths;
};

// Returns the first reachable markdown file, skipping SPA index.html fallbacks
// that a static server may return for a missing asset.
const fetchFirstMarkdown = async (paths: string[]): Promise<string | null> => {
  for (const path of paths) {
    try {
      const res = await fetch(path, { cache: 'no-cache' });
      if (!res.ok) continue;
      const contentType = res.headers.get('content-type') ?? '';
      if (contentType.includes('text/html')) continue;
      const text = await res.text();
      const head = text.trimStart().slice(0, 15).toLowerCase();
      if (head.startsWith('<!doctype') || head.startsWith('<html')) continue;
      if (text.trim() === '') continue;
      return text;
    } catch {
      // try next candidate
    }
  }
  return null;
};

const CustomHelpText: React.FC = () => {
  const { t, language } = useTranslation();
  const [content, setContent] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const text = await fetchFirstMarkdown(buildCandidatePaths(language));
      if (!cancelled) setContent(text);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [language]);

  if (content === undefined) {
    return null;
  }

  return (
    <div className="max-w-3xl">
      {content ? (
        <Markdown>{content}</Markdown>
      ) : (
        <div className="text-sm text-pc-gray-700">{t('about.help.fallback')}</div>
      )}
    </div>
  );
};

export default CustomHelpText;
