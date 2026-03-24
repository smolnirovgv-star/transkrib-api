import React from 'react';
import ReactDOM from 'react-dom/client';
import { LanguageProvider } from './i18n';
import { App } from './App';
import './globals.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </React.StrictMode>
);
