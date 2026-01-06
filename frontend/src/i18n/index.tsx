// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';

import { de } from '@/i18n/locales/de';
import { en } from '@/i18n/locales/en';

const translations = {
  en,
  de,
};

type TranslationVars = Record<string, string | number>;

type Language = keyof typeof translations;

type TranslationContextValue = {
  language: Language;
  availableLanguages: Array<{ key: Language; label: string }>;
  t: (key: string, defaultValue?: string | TranslationVars, vars?: TranslationVars) => string;
  changeLanguage: (next: string) => void;
};

const TranslationContext = createContext<TranslationContextValue | undefined>(undefined);

const normalizeLanguage = (value?: string): Language => {
  const normalized = value?.toLowerCase().split('-')[0];
  if (normalized && normalized in translations) {
    return normalized as Language;
  }
  return 'en';
};

const getFromPath = (resource: unknown, path: string): unknown =>
  path.split('.').reduce((acc: any, key: string) => {
    if (acc && typeof acc === 'object' && key in acc) {
      return acc[key];
    }
    return undefined;
  }, resource);

const applyReplacements = (value: string, vars?: Record<string, string | number>): string => {
  if (!vars) return value;
  return Object.keys(vars).reduce((acc, key) => {
    const regex = new RegExp(`{{\\s*${key}\\s*}}`, 'g');
    return acc.replace(regex, String(vars[key]));
  }, value);
};

const getInitialLanguage = (): Language => {
  if (typeof navigator !== 'undefined') {
    return normalizeLanguage(navigator.language);
  }
  return 'en';
};

export const I18nProvider: React.FC<PropsWithChildren> = ({ children }) => {
  const [language, setLanguage] = useState<Language>(getInitialLanguage);

  const changeLanguage = useCallback((next: string): void => {
    const normalized = normalizeLanguage(next);
    setLanguage(normalized);
  }, []);

  const translate = useCallback(
    (key: string, defaultValue?: string | TranslationVars, vars?: TranslationVars): string => {
      let finalDefault = defaultValue as string | undefined;
      let finalVars = vars;

      if (
        typeof defaultValue === 'object' &&
        defaultValue !== null &&
        !Array.isArray(defaultValue) &&
        vars === undefined
      ) {
        finalVars = defaultValue as TranslationVars;
        finalDefault = undefined;
      }

      const translation =
        getFromPath(translations[language], key) ??
        getFromPath(translations.en, key) ??
        finalDefault;

      if (typeof translation !== 'string') {
        return finalDefault ?? key;
      }

      return applyReplacements(translation, finalVars);
    },
    [language]
  );

  const value = useMemo<TranslationContextValue>(
    () => ({
      language,
      availableLanguages: (Object.keys(translations) as Language[]).map(lang => ({
        key: lang,
        label: translations[lang].languageName ?? lang,
      })),
      t: translate,
      changeLanguage,
    }),
    [language, changeLanguage, translate]
  );

  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>;
};

export const useTranslation = (): TranslationContextValue => {
  const ctx = useContext(TranslationContext);
  if (!ctx) {
    throw new Error('useTranslation must be used within an I18nProvider');
  }
  return ctx;
};
