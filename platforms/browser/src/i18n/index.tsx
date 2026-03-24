import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { ru, TranslationKey } from './ru';
import { en } from './en';
import { zh } from './zh';

export type Language = 'ru' | 'en' | 'zh';

type Translations = Record<TranslationKey, string>;

const translationsMap: Record<Language, Translations> = {
  ru,
  en: en as Translations,
  zh: zh as Translations,
};

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function getInitialLanguage(): Language {
  try {
    const stored = localStorage.getItem('transkrib-lang');
    if (stored && (stored === 'ru' || stored === 'en' || stored === 'zh')) {
      return stored;
    }
  } catch {
    // localStorage not available
  }
  return 'ru';
}

interface LanguageProviderProps {
  children: ReactNode;
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguageState] = useState<Language>(getInitialLanguage);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      localStorage.setItem('transkrib-lang', lang);
    } catch {
      // localStorage not available
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey): string => {
      return translationsMap[language][key] || translationsMap.ru[key] || key;
    },
    [language]
  );

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
}
