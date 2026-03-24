import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { createElement } from 'react';
import { ru, type TranslationKey } from './ru';
import { en } from './en';
import { zh } from './zh';

export type Language = 'ru' | 'en' | 'zh';

const translations: Record<Language, Record<string, string>> = {
  ru,
  en,
  zh,
};

const STORAGE_KEY = 'transkrib-lang';

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

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

export const LanguageContext = createContext<LanguageContextValue>({
  language: 'ru',
  setLanguage: () => {},
  t: (key: TranslationKey) => key,
});

interface LanguageProviderProps {
  children: ReactNode;
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // localStorage not available
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const t = useCallback(
    (key: TranslationKey): string => {
      const dict = translations[language];
      return dict[key] ?? key;
    },
    [language]
  );

  return createElement(
    LanguageContext.Provider,
    { value: { language, setLanguage, t } },
    children
  );
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
}

export type { TranslationKey };
