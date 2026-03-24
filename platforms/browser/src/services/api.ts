const API_BASE = '/api';

export interface TaskCreateResponse {
  task_id: string;
  state: string;
  source_type: string;
  source_name: string;
  created_at: string;
}

export interface TaskStatusResponse {
  task_id: string;
  state: string;
  progress: number;
  step: string;
  message: string;
  source_type: string;
  source_name: string;
  result_filename: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResultItem {
  filename: string;
  size: number;
  duration: number | null;
  created_at: string;
  task_id: string;
}

export interface SystemInfo {
  version: string;
  uptime: number;
  tasks_total: number;
  tasks_active: number;
  disk_free_mb: number;
}

export interface ProgressUpdate {
  state: string;
  progress: number;
  step: string;
  message: string;
  result_filename: string | null;
  error: string | null;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.text().catch(() => 'Unknown error');
    throw new Error(`API error ${response.status}: ${errorBody}`);
  }
  return response.json();
}

export const api = {
  async uploadFile(file: File): Promise<TaskCreateResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/tasks/upload`, {
      method: 'POST',
      body: formData,
    });

    return handleResponse<TaskCreateResponse>(response);
  },

  async submitUrl(url: string): Promise<TaskCreateResponse> {
    const response = await fetch(`${API_BASE}/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    return handleResponse<TaskCreateResponse>(response);
  },

  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const response = await fetch(`${API_BASE}/tasks/${taskId}`);
    return handleResponse<TaskStatusResponse>(response);
  },

  async listTasks(): Promise<TaskStatusResponse[]> {
    const response = await fetch(`${API_BASE}/tasks`);
    return handleResponse<TaskStatusResponse[]>(response);
  },

  async listResults(): Promise<ResultItem[]> {
    const response = await fetch(`${API_BASE}/results`);
    return handleResponse<ResultItem[]>(response);
  },

  getStreamUrl(filename: string): string {
    return `${API_BASE}/results/${encodeURIComponent(filename)}/stream`;
  },

  getDownloadUrl(filename: string): string {
    return `${API_BASE}/results/${encodeURIComponent(filename)}/download`;
  },

  async getSystemInfo(): Promise<SystemInfo> {
    const response = await fetch(`${API_BASE}/system/info`);
    return handleResponse<SystemInfo>(response);
  },
};
