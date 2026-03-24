import { contextBridge, ipcRenderer } from 'electron';

export interface ExportVideoOptions {
  sourceFilename: string;
  format: 'mp4' | 'mkv' | 'webm';
  crf: number;
  resolution: string;
  subtitleMode: 'embed' | 'srt' | 'both' | 'none';
  outputFolder: string;
}

export interface ElectronAPI {
  readFile: (filePath: string) => Promise<Uint8Array | null>;
  selectFile: () => Promise<string | null>;
  showNotification: (title: string, body: string) => Promise<boolean>;
  getAppVersion: () => Promise<string>;
  getBackendUrl: () => Promise<string>;
  setApiKey: (apiKey: string) => Promise<boolean>;
  getApiKey: () => Promise<string | null>;
  checkWhisperModel: () => Promise<{ downloaded: boolean; model?: string; size_mb?: number; error?: string }>;
  prepareWhisper: () => Promise<{ success?: boolean; status?: string; error?: string }>;
  pollBackendHealth: () => Promise<boolean>;
  uploadFile: (filePath: string, maxDurationSeconds?: number, whisperModel?: string) => Promise<{ task_id?: string; success?: boolean; error?: string }>;
  getTaskStatus: (taskId: string) => Promise<{
    task_id: string; state: string; current_step: string | null;
    progress_percent: number; step_details: string | null;
    result_filename: string | null; error_message: string | null;
  } | null>;
  submitUrl: (url: string, maxDurationSeconds?: number, whisperModel?: string) => Promise<{ task_id?: string; success?: boolean; error?: string }>;
  listResults: () => Promise<{ filename: string; size_mb: number; duration_seconds: number; duration_formatted: string; created_at: string }[]>;
  saveResult: (filename: string) => Promise<{ success: boolean; error?: string }>;
  checkLicense: () => Promise<{ licensed: boolean; error?: string }>;
  activateLicense: (licenseKey: string) => Promise<{ success: boolean; message?: string; error?: string }>;
  checkTrial: () => Promise<{
    state: 'new' | 'active' | 'warning' | 'expired' | 'blocked';
    remaining_days: number;
    today_count: number;
    daily_limit: number;
    warning?: boolean;
  }>;
  getResultPath: (filename: string) => Promise<string | null>;
  selectFolder: () => Promise<string | null>;
  exportVideo: (options: ExportVideoOptions) => Promise<{ success: boolean; outputPath?: string; error?: string }>;
  saveTranscript: (filename: string, format: 'txt' | 'srt' | 'json' | 'html') => Promise<{ success: boolean; error?: string }>;
  deleteResult: (filename: string) => Promise<{ success: boolean; error?: string }>;
  platform: string;
  windowMinimize: () => void;
  windowMaximize: () => void;
  windowClose: () => void;
  onWindowMaximized: (callback: (maximized: boolean) => void) => () => void;
  onDeepLink: (callback: (url: string) => void) => () => void;
  openExternal: (url: string) => void;
}

contextBridge.exposeInMainWorld('electronAPI', {
  readFile: (filePath: string): Promise<Uint8Array | null> => {
    return ipcRenderer.invoke('fs:readFile', filePath);
  },

  selectFile: (): Promise<string | null> => {
    return ipcRenderer.invoke('dialog:selectFile');
  },

  showNotification: (title: string, body: string): Promise<boolean> => {
    return ipcRenderer.invoke('notification:show', title, body);
  },

  getAppVersion: (): Promise<string> => {
    return ipcRenderer.invoke('app:version');
  },

  getBackendUrl: (): Promise<string> => {
    return ipcRenderer.invoke('app:backendUrl');
  },

  setApiKey: (apiKey: string): Promise<boolean> => {
    return ipcRenderer.invoke('app:setApiKey', apiKey);
  },

  getApiKey: (): Promise<string | null> => {
    return ipcRenderer.invoke('app:getApiKey');
  },

  checkWhisperModel: () => {
    return ipcRenderer.invoke('app:checkWhisperModel');
  },

  prepareWhisper: () => {
    return ipcRenderer.invoke('app:prepareWhisper');
  },

  pollBackendHealth: (): Promise<boolean> => {
    return ipcRenderer.invoke('app:pollBackendHealth');
  },

  uploadFile: (filePath: string, maxDurationSeconds?: number, whisperModel?: string) => {
    return ipcRenderer.invoke('app:uploadFile', filePath, maxDurationSeconds, whisperModel);
  },

  getTaskStatus: (taskId: string) => {
    return ipcRenderer.invoke('app:getTaskStatus', taskId);
  },

  submitUrl: (url: string, maxDurationSeconds?: number, whisperModel?: string) => {
    return ipcRenderer.invoke('app:submitUrl', url, maxDurationSeconds, whisperModel);
  },

  listResults: () => {
    return ipcRenderer.invoke('app:listResults');
  },

  saveResult: (filename: string) => {
    return ipcRenderer.invoke('app:saveResult', filename);
  },

  getResultPath: (filename: string): Promise<string | null> => {
    return ipcRenderer.invoke('app:getResultPath', filename);
  },

  checkLicense: () => {
    return ipcRenderer.invoke('app:checkLicense');
  },

  activateLicense: (licenseKey: string) => {
    return ipcRenderer.invoke('app:activateLicense', licenseKey);
  },

  checkTrial: () => {
    return ipcRenderer.invoke('app:checkTrial');
  },


  selectFolder: (): Promise<string | null> => {
    return ipcRenderer.invoke('dialog:selectFolder');
  },

  exportVideo: (options: ExportVideoOptions) => {
    return ipcRenderer.invoke('app:exportVideo', options);
  },

  saveTranscript: (filename: string, format: 'txt' | 'srt' | 'json' | 'html') => {
    return ipcRenderer.invoke('app:saveTranscript', filename, format);
  },

  deleteResult: (filename: string) => {
    return ipcRenderer.invoke('app:deleteResult', filename);
  },

  platform: process.platform,

  windowMinimize: (): void => {
    ipcRenderer.send('window:minimize');
  },

  windowMaximize: (): void => {
    ipcRenderer.send('window:maximize');
  },

  windowClose: (): void => {
    ipcRenderer.send('window:close');
  },

  onWindowMaximized: (callback: (maximized: boolean) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, maximized: boolean) => {
      callback(maximized);
    };
    ipcRenderer.on('window:maximized', handler);
    return () => {
      ipcRenderer.removeListener('window:maximized', handler);
    };
  },

  openExternal: (url: string): void => {
    ipcRenderer.send('shell:openExternal', url);
  },

  onDeepLink: (callback: (url: string) => void): (() => void) => {
    const handler = (_event: Electron.IpcRendererEvent, url: string) => {
      callback(url);
    };
    ipcRenderer.on('deep-link', handler);
    return () => {
      ipcRenderer.removeListener('deep-link', handler);
    };
  },
} satisfies ElectronAPI);
