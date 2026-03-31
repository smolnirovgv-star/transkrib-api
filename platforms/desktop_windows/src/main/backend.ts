/**
 * Backend lifecycle manager for standalone deployment.
 */

import { app } from "electron";
import * as path from "path";
import * as fs from "fs";
import { spawn, ChildProcess, execSync } from "child_process";

const isDev = !app.isPackaged;
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const HEALTH_CHECK_INTERVAL = 500;
const HEALTH_CHECK_TIMEOUT = 180000; // 3 min — backend kept alive even on timeout

let backendProcess: ChildProcess | null = null;
let backendPid: number | null = null;
let healthCheckTimer: NodeJS.Timeout | null = null;
let isQuitting = false;

// File logger — console.log invisible in packaged Electron apps
let _logPath: string | null = null;

export function initMainLog(): void {
  const storageDir = path.join(app.getPath("appData"), "Transkrib", "storage");
  const logDir = path.join(storageDir, "logs");
  try {
    if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    _logPath = path.join(logDir, "main.log");
    try {
      if (fs.existsSync(_logPath) && fs.statSync(_logPath).size > 100 * 1024) {
        fs.writeFileSync(_logPath, "");
      }
    } catch { /* ignore */ }
    log("=== Electron main process started ===");
    log(`isDev: ${isDev}`);
    log(`app.isPackaged: ${app.isPackaged}`);
    log(`process.resourcesPath: ${process.resourcesPath}`);
    log(`__dirname: ${__dirname}`);
  } catch (e) {
    _logPath = null;
    console.error("[Main] Failed to init log:", e);
  }
}

function log(msg: string): void {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  if (_logPath) { try { fs.appendFileSync(_logPath, line + "\n"); } catch { /* ignore */ } }
}

function logErr(msg: string): void {
  const line = `[${new Date().toISOString()}] ERROR: ${msg}`;
  console.error(line);
  if (_logPath) { try { fs.appendFileSync(_logPath, line + "\n"); } catch { /* ignore */ } }
}

function getBackendPath(): { cmd: string; args: string[]; cwd: string } {
  if (isDev) {
    const backendDir = path.join(__dirname, "../../../../backend");
    const scriptPath = path.join(backendDir, "standalone_server.py");
    log(`[Backend] DEV mode script: ${scriptPath}, exists: ${fs.existsSync(scriptPath)}`);
    if (!fs.existsSync(scriptPath)) throw new Error(`Backend script not found: ${scriptPath}`);
    return { cmd: "python", args: [scriptPath], cwd: backendDir };
  } else {
    const backendDir = path.join(process.resourcesPath, "backend");
    const exePath = path.join(backendDir, "backend.exe");
    log(`[Backend] PROD mode`);
    log(`[Backend] resourcesPath: ${process.resourcesPath}`);
    log(`[Backend] backendDir: ${backendDir} exists: ${fs.existsSync(backendDir)}`);
    log(`[Backend] exePath: ${exePath} exists: ${fs.existsSync(exePath)}`);
    try {
      const items = fs.readdirSync(backendDir);
      log(`[Backend] backendDir: [${items.slice(0, 6).join(", ")}]`);
    } catch (e) { logErr(`Cannot list backendDir: ${e}`); }
    if (!fs.existsSync(exePath)) throw new Error(`Backend executable not found: ${exePath}`);
    return { cmd: exePath, args: [], cwd: backendDir };
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const response = await fetch(`${BACKEND_URL}/api/system/health`, { signal: controller.signal });
    clearTimeout(timeout);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackend(): Promise<void> {
  const startTime = Date.now();
  let attempts = 0;
  while (Date.now() - startTime < HEALTH_CHECK_TIMEOUT) {
    const isHealthy = await checkHealth();
    attempts++;
    if (isHealthy) {
      log(`[Backend] Health check passed after ${attempts} attempts, ${Date.now() - startTime}ms`);
      return;
    }
    if (attempts % 20 === 0) {
      log(`[Backend] Still waiting... attempt ${attempts}, ${Date.now() - startTime}ms elapsed`);
      if (!backendProcess) {
        logErr("[Backend] Process died during health check wait");
        throw new Error("Backend process died during startup");
      }
    }
    await new Promise((resolve) => setTimeout(resolve, HEALTH_CHECK_INTERVAL));
  }
  logErr(`[Backend] Timed out after ${HEALTH_CHECK_TIMEOUT}ms`);
  throw new Error("Backend failed to become healthy within timeout");
}

function is32BitWindowsOS(): boolean {
  if (process.platform !== "win32") return false;
  if (process.env.PROCESSOR_ARCHITEW6432) return false;
  return process.env.PROCESSOR_ARCHITECTURE === "x86";
}

export async function startBackend(): Promise<void> {
  if (backendProcess) { log("[Backend] Already running"); return; }

  if (is32BitWindowsOS()) {
    throw new Error(
      "Transkrib requires a 64-bit version of Windows.\n\n" +
      "The AI engine (Whisper / PyTorch) does not support 32-bit operating systems.\n" +
      "Please install the 64-bit version of Windows to use Transkrib."
    );
  }

  const { cmd, args, cwd } = getBackendPath();
  log(`[Backend] Starting... cmd: ${cmd}`);
  log(`[Backend] CWD: ${cwd}`);

  const storageDir = path.join(app.getPath("appData"), "Transkrib", "storage");
  log(`[Backend] APP_STORAGE_DIR: ${storageDir}`);

  if (!fs.existsSync(storageDir)) fs.mkdirSync(storageDir, { recursive: true });

  const env = {
    ...process.env,
    TRANSKRIB_PORT: BACKEND_PORT.toString(),
    APP_STORAGE_DIR: storageDir,
    PYTHONUNBUFFERED: "1",
    PYTHONUTF8: "1",
    PYTHONDONTWRITEBYTECODE: "1",
  };

  backendProcess = spawn(cmd, args, { cwd, env, windowsHide: true, detached: false });
  backendPid = backendProcess.pid || null;
  log(`[Backend] Spawned PID: ${backendPid}`);

  backendProcess.stdout?.on("data", (data) => log(`[Backend OUT] ${data.toString().trim()}`));
  backendProcess.stderr?.on("data", (data) => log(`[Backend ERR] ${data.toString().trim()}`));

  backendProcess.on("exit", (code, signal) => {
    log(`[Backend] Process exited code=${code} signal=${signal}`);
    backendProcess = null;
    backendPid = null;
    if (code !== 0 && !isQuitting) {
      log("[Backend] Unexpected exit, restarting in 2s...");
      setTimeout(() => startBackend().catch((e) => logErr(`Restart failed: ${e}`)), 2000);
    }
  });

  backendProcess.on("error", (err) => {
    logErr(`[Backend] Spawn error: ${err}`);
    backendProcess = null;
    backendPid = null;
  });

  const _t0 = Date.now();
  try {
    log("[Backend] Waiting for health check...");
    await waitForBackend();
    log(`[Backend] Ready at ${BACKEND_URL} after ${Date.now() - _t0}ms`);
  } catch (error) {
    // Health check timed out — but backend process is still running.
    // BackendStartup.tsx in the renderer polls independently and will
    // call onReady() once the backend eventually responds.
    // Do NOT kill the backend here.
    logErr(`[Backend] Health check timed out (process still running): ${error}`);
    throw error;
  }
}

export function stopBackend(): void {
  isQuitting = true;
  if (healthCheckTimer) { clearInterval(healthCheckTimer); healthCheckTimer = null; }
  if (!backendProcess && !backendPid) { log("[Backend] No process to stop"); return; }
  log("[Backend] Stopping...");
  try {
    if (process.platform === "win32" && backendPid) {
      try {
        execSync(`taskkill /pid ${backendPid} /t /f`, { stdio: "ignore" });
        log("[Backend] Killed via taskkill");
      } catch (err) {
        logErr(`taskkill failed: ${err}`);
        backendProcess?.kill("SIGKILL");
      }
    } else if (backendProcess) {
      process.kill(-backendProcess.pid!, "SIGTERM");
      log("[Backend] Killed via SIGTERM");
    }
  } catch (error) { logErr(`Error killing: ${error}`); }
  backendProcess = null;
  backendPid = null;
}

export function getBackendUrl(): string { return BACKEND_URL; }
export function isBackendRunning(): boolean { return backendProcess !== null; }

// Keep-alive: будим Render при старте и пингуем каждые 10 минут
const RENDER_URL = 'https://transkrib-api.onrender.com/api/system/license';
const pingRender = () => {
  const https = require('https');
  https.get(RENDER_URL, (res: any) => res.resume()).on('error', () => {});
};
// Будим сразу при старте приложения
setTimeout(pingRender, 2000);
// Пингуем каждые 10 минут чтобы не засыпал
setInterval(pingRender, 10 * 60 * 1000);
