import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ru } from './ru';
import { en } from './en';
import { zh } from './zh';

const translations = { ru, en, zh } as const;
export type Language = keyof typeof translations;
type TranslationKey = keyof typeof ru;

interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

const I18nContext = createContext<I18nContextType>(null!);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLang] = useState<Language>('ru');

  useEffect(() => {
    AsyncStorage.getItem('transkrib-lang').then((v) => {
      if (v) setLang(v as Language);
    });
  }, []);

  const setLanguage = (l: Language) => {
    setLang(l);
    AsyncStorage.setItem('transkrib-lang', l);
  };

  const t = (key: TranslationKey) =>
    translations[language]?.[key] || translations.ru[key] || key;

  return React.createElement(
    I18nContext.Provider,
    { value: { language, setLanguage, t } },
    children,
  );
};

export const useTranslation = () => useContext(I18nContext);
