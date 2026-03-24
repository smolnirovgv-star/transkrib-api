import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { LanguageProvider } from './src/i18n';
import { ThemeProvider } from './src/theme';
import { RootNavigator } from './src/navigation/RootNavigator';

const navigationDarkTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: '#6C63FF',
    background: '#0f0c29',
    card: '#16213e',
    text: '#e0e0e0',
    border: '#1a1a2e',
    notification: '#FF6584',
  },
};

export default function App(): React.JSX.Element {
  return (
    <LanguageProvider>
      <ThemeProvider>
        <NavigationContainer theme={navigationDarkTheme}>
          <StatusBar style="light" />
          <RootNavigator />
        </NavigationContainer>
      </ThemeProvider>
    </LanguageProvider>
  );
}
