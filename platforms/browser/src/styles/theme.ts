import { useState, useEffect, useCallback } from 'react';

export interface ThemeColors {
  primary: string;
  primaryLight: string;
  primaryDark: string;
  accent: string;
  accentLight: string;
  accentDark: string;
  glassBg: string;
  glassBgHover: string;
  glassBorder: string;
  glassShadow: string;
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  bgGradientStart: string;
  bgGradientMid: string;
  bgGradientEnd: string;
  success: string;
  warning: string;
  error: string;
  info: string;
}

export interface Theme {
  name: 'dark' | 'light';
  colors: ThemeColors;
}

export const darkTheme: Theme = {
  name: 'dark',
  colors: {
    primary: '#6C63FF',
    primaryLight: '#8B83FF',
    primaryDark: '#5A52E0',
    accent: '#FF6584',
    accentLight: '#FF8FA3',
    accentDark: '#E0506E',
    glassBg: 'rgba(255, 255, 255, 0.08)',
    glassBgHover: 'rgba(255, 255, 255, 0.12)',
    glassBorder: 'rgba(255, 255, 255, 0.15)',
    glassShadow: '0 8px 32px rgba(0, 0, 0, 0.37)',
    textPrimary: '#ffffff',
    textSecondary: 'rgba(255, 255, 255, 0.7)',
    textTertiary: 'rgba(255, 255, 255, 0.45)',
    bgGradientStart: '#0f0c29',
    bgGradientMid: '#302b63',
    bgGradientEnd: '#24243e',
    success: '#4CAF50',
    warning: '#FFC107',
    error: '#F44336',
    info: '#2196F3',
  },
};

export const lightTheme: Theme = {
  name: 'light',
  colors: {
    primary: '#6C63FF',
    primaryLight: '#8B83FF',
    primaryDark: '#5A52E0',
    accent: '#FF6584',
    accentLight: '#FF8FA3',
    accentDark: '#E0506E',
    glassBg: 'rgba(255, 255, 255, 0.6)',
    glassBgHover: 'rgba(255, 255, 255, 0.75)',
    glassBorder: 'rgba(255, 255, 255, 0.5)',
    glassShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
    textPrimary: '#1a1a2e',
    textSecondary: 'rgba(26, 26, 46, 0.7)',
    textTertiary: 'rgba(26, 26, 46, 0.45)',
    bgGradientStart: '#e8e6f0',
    bgGradientMid: '#d5d0e5',
    bgGradientEnd: '#e0dce8',
    success: '#4CAF50',
    warning: '#FFC107',
    error: '#F44336',
    info: '#2196F3',
  },
};

const THEME_STORAGE_KEY = 'transkrib-theme';

function getInitialTheme(): 'dark' | 'light' {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') {
      return stored;
    }
    // Respect system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
  } catch {
    // localStorage or matchMedia not available
  }
  return 'dark';
}

function applyThemeClass(themeName: 'dark' | 'light') {
  const root = document.documentElement;
  if (themeName === 'light') {
    root.classList.add('theme-light');
    root.classList.remove('theme-dark');
    document.body.classList.add('theme-light');
    document.body.classList.remove('theme-dark');
  } else {
    root.classList.add('theme-dark');
    root.classList.remove('theme-light');
    document.body.classList.add('theme-dark');
    document.body.classList.remove('theme-light');
  }
}

export function useTheme() {
  const [themeName, setThemeNameState] = useState<'dark' | 'light'>(getInitialTheme);

  const theme = themeName === 'dark' ? darkTheme : lightTheme;

  useEffect(() => {
    applyThemeClass(themeName);
  }, [themeName]);

  // Listen for system preference changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const handler = (e: MediaQueryListEvent) => {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      // Only auto-switch if user hasn't explicitly set a preference
      if (!stored) {
        setThemeNameState(e.matches ? 'light' : 'dark');
      }
    };
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  const setTheme = useCallback((name: 'dark' | 'light') => {
    setThemeNameState(name);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, name);
    } catch {
      // localStorage not available
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(themeName === 'dark' ? 'light' : 'dark');
  }, [themeName, setTheme]);

  return {
    theme,
    themeName,
    isDark: themeName === 'dark',
    isLight: themeName === 'light',
    setTheme,
    toggleTheme,
  };
}
