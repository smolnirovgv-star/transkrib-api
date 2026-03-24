import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  Notification,
  nativeImage,
  session,
  protocol,
  net,
  shell,
} from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { createTray } from './tray';
import { startBackend, stopBackend, getBackendUrl, initMainLog, checkHealth } from './backend';

const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;

const iconPath = path.join(__dirname, '../../build/icon.png');
const appIcon = fs.existsSync(iconPath) ? iconPath : undefined;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: 'hidden',
    titleBarOverlay: false,
    frame: false,
    transparent: false,
    backgroundColor: '#00000000',
    show: false,
    ...(appIcon ? { icon: appIcon } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window:maximized', true);
  });

  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window:maximized', false);
  });
}

function registerIpcHandlers(): void {
  ipcMain.handle('fs:readFile', async (_event, filePath: string) => {
    try {
      return fs.readFileSync(filePath);
    } catch (error) {
      console.error('[Main] Failed to read file:', error);
      return null;
    }
  });

  ipcMain.handle('dialog:selectFile', async () => {
    if (!mainWindow) return null;

    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Выберите видео файл',
      filters: [
        {
          name: 'Video Files',
          extensions: [
            'mp4',
            'mkv',
            'avi',
            'mov',
            'wmv',
            'flv',
            'webm',
            'ts',
            'm4v',
          ],
        },
        { name: 'All Files', extensions: ['*'] },
      ],
      properties: ['openFile'],
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });

  ipcMain.handle(
    'notification:show',
    async (_event, title: string, body: string) => {
      if (Notification.isSupported()) {
        const notification = new Notification({
          title,
          body,
          ...(appIcon ? { icon: appIcon } : {}),
        });
        notification.show();
      }
      return true;
    }
  );

  ipcMain.handle('app:version', async () => {
    return app.getVersion();
  });

  ipcMain.handle('app:backendUrl', async () => {
    return getBackendUrl();
  });

  ipcMain.handle('app:setApiKey', async (_event, apiKey: string) => {
    const configPath = path.join(app.getPath('appData'), 'Transkrib', 'config.json');
    const configDir = path.dirname(configPath);

    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }

    let config: Record<string, any> = {};
    if (fs.existsSync(configPath)) {
      try {
        config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      } catch (error) {
        console.error('[Main] Failed to parse config:', error);
      }
    }

    config.anthropic_api_key = apiKey;
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');

    return true;
  });

  ipcMain.handle('app:getApiKey', async () => {
    const configPath = path.join(app.getPath('appData'), 'Transkrib', 'config.json');

    if (!fs.existsSync(configPath)) {
      return null;
    }

    try {
      const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      return config.anthropic_api_key || null;
    } catch (error) {
      console.error('[Main] Failed to read config:', error);
      return null;
    }
  });

  ipcMain.handle('app:checkWhisperModel', async () => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/system/whisper-status`);
      if (!response.ok) {
        return { downloaded: false, error: 'Failed to check status' };
      }
      return await response.json();
    } catch (error) {
      console.error('[Main] Failed to check Whisper status:', error);
      return { downloaded: false, error: String(error) };
    }
  });

  ipcMain.handle('app:prepareWhisper', async () => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/system/prepare-whisper`, {
        method: 'POST',
      });
      if (!response.ok) {
        return { success: false, error: 'Failed to start download' };
      }
      return await response.json();
    } catch (error) {
      console.error('[Main] Failed to prepare Whisper:', error);
      return { success: false, error: String(error) };
    }
  });

  // Health-check proxy — renderer calls this instead of direct fetch (avoids CORS issues)
  ipcMain.handle('app:pollBackendHealth', async () => {
    const ok = await checkHealth();
    return ok;
  });

  // Upload a local file to the backend via main process (avoids renderer CORS/PNA restrictions)
  ipcMain.handle('app:uploadFile', async (_event, filePath: string, maxDurationSeconds?: number, whisperModel?: string) => {
    try {
      const fileBuffer = await fs.promises.readFile(filePath);
      const blob = new Blob([fileBuffer]);
      const form = new FormData();
      form.append('file', blob, path.basename(filePath));
      if (maxDurationSeconds) form.append('max_duration_seconds', String(maxDurationSeconds));
      if (whisperModel) form.append('whisper_model', whisperModel);
      const response = await fetch(`${getBackendUrl()}/api/tasks/upload`, { method: 'POST', body: form });
      if (!response.ok) {
        const text = await response.text();
        let msg = text;
        try { msg = JSON.parse(text).detail || text; } catch {}
        return { success: false, error: msg };
      }
      return { ...(await response.json() as object), success: true };
    } catch (e: any) {
      console.error('[Main] uploadFile error:', e);
      return { success: false, error: String(e) };
    }
  });

  ipcMain.handle('app:getTaskStatus', async (_event, taskId: string) => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/tasks/${taskId}`);
      if (!response.ok) return null;
      return response.json();
    } catch { return null; }
  });

  ipcMain.handle('app:submitUrl', async (_event, url: string, maxDurationSeconds?: number, whisperModel?: string) => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/tasks/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, max_duration_seconds: maxDurationSeconds ?? null, whisper_model: whisperModel ?? null }),
      });
      if (!response.ok) {
        const text = await response.text();
        let msg = text;
        try { msg = JSON.parse(text).detail || text; } catch {}
        return { success: false, error: msg };
      }
      return { ...(await response.json() as object), success: true };
    } catch (e: any) {
      return { success: false, error: String(e) };
    }
  });

  ipcMain.handle('app:listResults', async () => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/results/`);
      if (!response.ok) return [];
      return response.json();
    } catch { return []; }
  });

  // Save a result video to user-chosen location
  ipcMain.handle('app:saveResult', async (_event, filename: string) => {
    const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
    const srcPath = path.join(storageDir, 'results', filename);
    if (!fs.existsSync(srcPath)) return { success: false, error: 'File not found' };

    const { canceled, filePath: destPath } = await dialog.showSaveDialog({
      title: 'Сохранить видео',
      defaultPath: path.join(app.getPath('downloads'), filename),
      filters: [{ name: 'Video', extensions: ['mp4'] }, { name: 'All Files', extensions: ['*'] }],
    });
    if (canceled || !destPath) return { success: false, error: 'Cancelled' };

    try {
      fs.copyFileSync(srcPath, destPath);
      shell.showItemInFolder(destPath);
      return { success: true };
    } catch (e: any) {
      return { success: false, error: String(e) };
    }
  });

  ipcMain.handle('app:checkLicense', async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5000);
      const response = await fetch(`${getBackendUrl()}/api/system/license`, { signal: ctrl.signal });
      clearTimeout(t);
      if (!response.ok) {
        return { licensed: false, error: 'Failed to check license' };
      }
      return await response.json();
    } catch (error) {
      console.error('[Main] Failed to check license:', error);
      return { licensed: false, error: String(error) };
    }
  });

  ipcMain.handle('app:checkTrial', async () => {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5000);
      const response = await fetch(`${getBackendUrl()}/api/system/trial`, { signal: ctrl.signal });
      clearTimeout(t);
      if (!response.ok) {
        return { state: 'new', remaining_days: 7, today_count: 0, daily_limit: 3 };
      }
      return await response.json();
    } catch (error) {
      console.error('[Main] Failed to check trial:', error);
      return { state: 'new', remaining_days: 7, today_count: 0, daily_limit: 3 };
    }
  });

  ipcMain.handle('app:activateLicense', async (_event, licenseKey: string) => {
    try {
      const response = await fetch(`${getBackendUrl()}/api/system/activate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: licenseKey }),
      });

      const result = await response.json() as { detail?: string; message?: string };

      if (!response.ok) {
        return { success: false, error: result.detail || 'Activation failed' };
      }

      return { success: true, message: result.message };
    } catch (error) {
      console.error('[Main] Failed to activate license:', error);
      return { success: false, error: String(error) };
    }
  });

  ipcMain.on('shell:openExternal', (_event, url: string) => {
    shell.openExternal(url);
  });

  ipcMain.handle('app:getResultPath', async (_event, filename: string) => {
    const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
    const filePath = path.join(storageDir, 'results', filename);
    if (!fs.existsSync(filePath)) return null;
    return filePath;
  });

  ipcMain.handle('app:deleteResult', async (_event, filename: string) => {
    try {
      const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
      const filePath = path.join(storageDir, 'results', filename);
      if (!fs.existsSync(filePath)) return { success: false, error: 'File not found' };
      fs.unlinkSync(filePath);
      // Also remove associated transcript if exists
      const stem = filename.replace(/\.mp4$/i, '');
      const txPath = path.join(storageDir, 'processing', stem + '_transcript.json');
      if (fs.existsSync(txPath)) fs.unlinkSync(txPath);
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e?.message || 'Delete failed' };
    }
  });


  // Select a folder for export output

  // Save transcript to user-chosen file
  ipcMain.handle('app:saveTranscript', async (_event, filename: string, format: string) => {
    const extMap: Record<string, string> = { txt: 'txt', srt: 'srt', json: 'json', html: 'html' };
    const ext = extMap[format] || 'txt';
    const stem = filename.replace(/\.mp4$/i, '');
    const { canceled, filePath: destPath } = await dialog.showSaveDialog({
      title: 'Сохранить транскрипт',
      defaultPath: path.join(app.getPath('downloads'), `${stem}.${ext}`),
      filters: [{ name: 'Text', extensions: [ext] }, { name: 'All Files', extensions: ['*'] }],
    });
    if (canceled || !destPath) return { success: false };
    try {
      const backendUrl = getBackendUrl();
      const res = await fetch(`${backendUrl}/api/transcript/${encodeURIComponent(filename)}/download?format=${format}`);
      if (!res.ok) return { success: false, error: 'Backend error' };
      const text = await res.text();
      fs.writeFileSync(destPath, text, 'utf-8');
      return { success: true };
    } catch (e: any) {
      return { success: false, error: e.message };
    }
  });

  ipcMain.handle('dialog:selectFolder', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select output folder',
      properties: ['openDirectory', 'createDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
  });

  // Export video with quality settings via backend
  ipcMain.handle('app:exportVideo', async (_event, options: {
    sourceFilename: string;
    format: string;
    crf: number;
    resolution: string;
    subtitleMode: string;
    outputFolder: string;
  }) => {
    try {
      const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
      const srcPath = path.join(storageDir, 'results', options.sourceFilename);
      if (!fs.existsSync(srcPath)) {
        return { success: false, error: 'Source file not found' };
      }

      // Build output filename
      const baseName = path.basename(options.sourceFilename, path.extname(options.sourceFilename));
      const outName = `${baseName}_export.${options.format}`;
      let outputPath: string;

      if (options.outputFolder) {
        outputPath = path.join(options.outputFolder, outName);
      } else {
        // Show save dialog if no folder chosen
        const { canceled, filePath } = await dialog.showSaveDialog({
          title: 'Export video',
          defaultPath: path.join(app.getPath('downloads'), outName),
          filters: [
            { name: 'Video', extensions: [options.format] },
            { name: 'All Files', extensions: ['*'] },
          ],
        });
        if (canceled || !filePath) return { success: false, error: 'Cancelled' };
        outputPath = filePath;
      }

      // Call backend export endpoint
      const response = await fetch(`${getBackendUrl()}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_filename: options.sourceFilename,
          output_path: outputPath,
          format: options.format,
          crf: options.crf,
          resolution: options.resolution,
          subtitle_mode: options.subtitleMode,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        let msg = text;
        try { msg = JSON.parse(text).detail || text; } catch {}
        return { success: false, error: msg };
      }

      const result = await response.json() as { output_path?: string };
      shell.showItemInFolder(outputPath);
      return { success: true, outputPath: result.output_path || outputPath };
    } catch (e: any) {
      console.error('[Main] exportVideo error:', e);
      return { success: false, error: String(e) };
    }
  });

  ipcMain.on('window:minimize', () => {
    mainWindow?.minimize();
  });

  ipcMain.on('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });

  ipcMain.on('window:close', () => {
    mainWindow?.close();
  });
}

// Register custom scheme for serving local result files (video playback without CORS)
protocol.registerSchemesAsPrivileged([
  { scheme: 'transkrib', privileges: { secure: true, standard: true, supportFetchAPI: true, stream: true } },
]);

app.setAsDefaultProtocolClient('transkrib');

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (_event: Electron.Event, commandLine: string[]) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
    const deepLink = commandLine.find((arg) => arg.startsWith('transkrib://'));
    if (deepLink && mainWindow) {
      mainWindow.webContents.send('deep-link', deepLink);
    }
  });

  app.on('open-url', (event, url) => {
    event.preventDefault();
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
      mainWindow.webContents.send('deep-link', url);
    }
  });

  app.whenReady().then(async () => {
    initMainLog(); // Write main process logs to AppData/Transkrib/storage/logs/main.log

    // Serve local result files via transkrib:// scheme (bypasses CORS/PNA for video <src>)
    protocol.handle('transkrib', (request) => {
      const url = new URL(request.url);
      // transkrib://results/filename.mp4 → AppData/Transkrib/storage/results/filename.mp4
      const filename = decodeURIComponent(url.pathname.replace(/^\//, ''));
      const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
      const filePath = path.join(storageDir, 'results', filename);
      return net.fetch('file:///' + filePath.split(path.sep).join('/'));
    });
    if (isDev) {
      session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
        callback({
          responseHeaders: {
            ...details.responseHeaders,
            'Content-Security-Policy': [
              "default-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:* https://*.supabase.co wss://*.supabase.co; media-src 'self' http://localhost:* http://127.0.0.1:* blob:",
            ],
          },
        });
      });
    }

    // Open window IMMEDIATELY — BackendStartup.tsx shows spinner while backend loads
    createWindow();
    registerIpcHandlers();
    if (mainWindow) createTray(mainWindow);

    // Start backend in background — window already shows spinner via BackendStartup.tsx
    startBackend().catch((err) => {
      // Backend timed out but process is still running — BackendStartup.tsx keeps polling
      console.error('[Main] Backend startup warning:', err);
    });
  });

  app.on('window-all-closed', () => {
    stopBackend();
    app.quit();
  });

  app.on('before-quit', () => {
    stopBackend();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
}
