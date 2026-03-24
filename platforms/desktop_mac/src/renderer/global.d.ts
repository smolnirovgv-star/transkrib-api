declare module '*.svg' {
  const content: string;
  export default content;
}

import { ElectronAPI } from '../main/preload';

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};
