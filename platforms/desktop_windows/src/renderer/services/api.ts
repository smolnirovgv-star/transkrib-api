const getBaseUrl = (): string =>
  localStorage.getItem('transkrib-backend-url') || 'http://127.0.0.1:8000';

async function fetchWithRetry(
  url: string,
  init?: RequestInit,
  maxRetries = 3,
  retryDelayMs = 2000,
): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fetch(url, init);
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
      }
    }
  }
  throw lastError;
}

export interface TaskResponse {
  task_id: string;
  status?: string;
  message?: string;
}

export interface TaskStatus {
  task_id: string;
  state: string;
  current_step: string | null;
  progress_percent: number;
  step_details: string | null;
  result_filename: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResultItem {
  filename: string;
  size_mb: number;
  duration_seconds: number;
  duration_formatted: string;
  created_at: string;
}

export const api = {
  async uploadFile(file: File, maxDurationSeconds?: number, whisperModel?: string): Promise<TaskResponse> {
    const _url = getBaseUrl() + '/api/tasks/upload';
    console.log('[API] uploadFile url:', _url, 'localStorage:', localStorage.getItem('transkrib-backend-url'));
    const form = new FormData();
    form.append('file', file);
    if (maxDurationSeconds) form.append('max_duration_seconds', String(maxDurationSeconds));
    if (whisperModel) form.append('whisper_model', whisperModel);
    const res = await fetchWithRetry(`${getBaseUrl()}/api/tasks/upload`, { method: 'POST', body: form });
    if (!res.ok) {
      const body = await res.text();
      let message = body;
      try { const j = JSON.parse(body); message = j.detail || body; } catch {}
      throw new Error(message);
    }
    return res.json();
  },

  async submitUrl(url: string, maxDurationSeconds?: number, whisperModel?: string): Promise<TaskResponse> {
    const res = await fetchWithRetry(`${getBaseUrl()}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, max_duration_seconds: maxDurationSeconds ?? null, whisper_model: whisperModel ?? null }),
    });
    if (!res.ok) {
      const body = await res.text();
      let message = body;
      try { const j = JSON.parse(body); message = j.detail || body; } catch {}
      throw new Error(message);
    }
    return res.json();
  },

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const res = await fetchWithRetry(`${getBaseUrl()}/api/tasks/${taskId}`, undefined, 2, 1000);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listResults(): Promise<ResultItem[]> {
    const res = await fetchWithRetry(`${getBaseUrl()}/api/results/`, undefined, 2, 1000);
    if (!res.ok) return [];
    return res.json();
  },

  getStreamUrl(filename: string): string {
    return `${getBaseUrl()}/api/results/${encodeURIComponent(filename)}/stream`;
  },

  getDownloadUrl(filename: string): string {
    return `${getBaseUrl()}/api/results/${filename}/download`;
  },

  async deleteResult(filename: string): Promise<boolean> {
    try {
      const res = await fetch(`${getBaseUrl()}/api/results/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      return res.ok;
    } catch { return false; }
  },

  getWsUrl(taskId: string): string {
    const base = getBaseUrl().replace(/^http/, 'ws');
    return `${base}/ws/tasks/${taskId}/progress`;
  },
  async generatePreview(filename: string): Promise<string | null> {
    try {
      const res = await fetchWithRetry(`${getBaseUrl()}/api/preview/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (!data.preview_url) return null;
      return `${getBaseUrl()}${data.preview_url}?t=${Date.now()}`;
    } catch {
      return null;
    }
  },

  async getTranscript(filename: string): Promise<{ segments: any[]; count: number; formatted_text?: string } | null> {
    try {
      const res = await fetchWithRetry(`${getBaseUrl()}/api/transcript/${encodeURIComponent(filename)}`, undefined, 2, 1000);
      if (!res.ok) return null;
      return res.json();
    } catch { return null; }
  },

  getTranscriptDownloadUrl(filename: string, format: 'txt' | 'srt' | 'json' | 'html'): string {
    return `${getBaseUrl()}/api/transcript/${encodeURIComponent(filename)}/download?format=${format}`;
  },

  getPreviewImageUrl(previewUrl: string): string {
    const base = getBaseUrl();
    return `${base}${previewUrl}?t=${Date.now()}`;
  },

};
