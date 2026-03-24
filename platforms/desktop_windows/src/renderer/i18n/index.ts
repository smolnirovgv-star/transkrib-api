import React, { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react';
import ru, { type TranslationKeys } from './ru';
import en from './en';
import zh from './zh';

export type Language = 'ru' | 'en' | 'zh';

const translations: Record<Language, TranslationKeys> = { ru, en, zh };

type NestedKeyOf<T> = T extends object
  ? {
      [K in keyof T & string]: T[K] extends object
        ? `${K}.${NestedKeyOf<T[K]>}`
        : K;
    }[keyof T & string]
  : never;

export type TranslationKey = NestedKeyOf<TranslationKeys>;

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const keys = path.split('.');
  let current: unknown = obj;

  for (const key of keys) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return path;
    }
    current = (current as Record<string, unknown>)[key];
  }

  return typeof current === 'string' ? current : path;
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
  availableLanguages: Language[];
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = 'transkrib-language';

function getInitialLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && (stored === 'ru' || stored === 'en' || stored === 'zh')) {
      return stored as Language;
    }
  } catch {
    // localStorage not available
  }
  return 'ru';
}

export function LanguageProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // localStorage not available
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey): string => {
      return getNestedValue(
        translations[language] as unknown as Record<string, unknown>,
        key
      );
    },
    [language]
  );

  const availableLanguages = useMemo<Language[]>(() => ['ru', 'en', 'zh'], []);

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage,
      t,
      availableLanguages,
    }),
    [language, setLanguage, t, availableLanguages]
  );

  return React.createElement(LanguageContext.Provider, { value }, children);
}

export function useTranslation(): LanguageContextValue {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
}

export { type TranslationKeys };
export default translations;
