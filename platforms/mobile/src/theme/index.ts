import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const THEME_STORAGE_KEY = 'transkrib-theme';

export interface AppTheme {
  background: string;
  surface: string;
  card: string;
  text: string;
  textSecondary: string;
  primary: string;
  accent: string;
  success: string;
  error: string;
  border: string;
  inputBackground: string;
  tabBar: string;
}

export type ThemeMode = 'dark' | 'light' | 'system';

export const darkTheme: AppTheme = {
  background: '#0f0c29',
  surface: '#1a1a2e',
  card: '#16213e',
  text: '#e0e0e0',
  textSecondary: '#8888a0',
  primary: '#6C63FF',
  accent: '#FF6584',
  success: '#4CAF50',
  error: '#FF5252',
  border: '#2a2a4e',
  inputBackground: '#1a1a2e',
  tabBar: '#0f0c29',
};

export const lightTheme: AppTheme = {
  background: '#f5f5ff',
  surface: '#ffffff',
  card: '#eeeef6',
  text: '#1a1a2e',
  textSecondary: '#6a6a8a',
  primary: '#6C63FF',
  accent: '#FF6584',
  success: '#4CAF50',
  error: '#FF5252',
  border: '#d0d0e0',
  inputBackground: '#eeeef6',
  tabBar: '#ffffff',
};

interface ThemeContextValue {
  theme: AppTheme;
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: darkTheme,
  themeMode: 'dark',
  setThemeMode: () => {},
  isDark: true,
});

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps): React.JSX.Element {
  const [themeMode, setThemeModeState] = useState<ThemeMode>('dark');

  useEffect(() => {
    AsyncStorage.getItem(THEME_STORAGE_KEY).then((stored) => {
      if (stored === 'dark' || stored === 'light' || stored === 'system') {
        setThemeModeState(stored);
      }
    });
  }, []);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemeModeState(mode);
    AsyncStorage.setItem(THEME_STORAGE_KEY, mode);
  }, []);

  const isDark = themeMode === 'dark' || themeMode === 'system';
  const theme = isDark ? darkTheme : lightTheme;

  const value: ThemeContextValue = {
    theme,
    themeMode,
    setThemeMode,
    isDark,
  };

  return React.createElement(ThemeContext.Provider, { value }, children);
}

export function useAppTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useAppTheme must be used within a ThemeProvider');
  }
  return context;
}
