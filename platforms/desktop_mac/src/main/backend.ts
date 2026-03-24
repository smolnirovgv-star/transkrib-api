/**
 * Backend URL configuration for macOS.
 * macOS version uses the remote Render.com API instead of a local backend process.
 */

import { app } from 'electron';
import * as path from 'path';
import * as fs from 'fs';

// Remote API — no local backend process on macOS
const API_BASE_URL = process.env.VITE_API_URL || 'https://transkrib-api.onrender.com';

let _logPath: string | null = null;

export function initMainLog(): void {
  const storageDir = path.join(app.getPath('appData'), 'Transkrib', 'storage');
  const logDir = path.join(storageDir, 'logs');
  try {
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    _logPath = path.join(logDir, 'main.log');
    try {
      if (fs.existsSync(_logPath) && fs.statSync(_logPath).size > 100 * 1024) {
        fs.writeFileSync(_logPath, '');
      }
    } catch { /* ignore */ }
    log('=== Electron main process started (macOS) ===');
    log(`API_BASE_URL: ${API_BASE_URL}`);
  } catch (e) {
    _logPath = null;
    console.error('[Main] Failed to init log:', e);
  }
}

function log(msg: string): void {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  if (_logPath) { try { fs.appendFileSync(_logPath, line + '\n'); } catch { /* ignore */ } }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(`${API_BASE_URL}/api/system/health`, { signal: controller.signal });
    clearTimeout(timeout);
    return response.ok;
  } catch {
    return false;
  }
}

export async function startBackend(): Promise<void> {
  // macOS uses remote API — no local process to start
  log(`[Backend] macOS mode — remote API: ${API_BASE_URL}`);
}

export function stopBackend(): void {
  // macOS uses remote API — nothing to stop
}

export function getBackendUrl(): string { return API_BASE_URL; }
export function isBackendRunning(): boolean { return true; }
