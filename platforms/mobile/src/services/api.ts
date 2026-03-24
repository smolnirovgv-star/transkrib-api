import AsyncStorage from '@react-native-async-storage/async-storage';

let cachedUrl: string | null = null;

const getBaseUrl = async (): Promise<string> => {
  if (!cachedUrl) {
    cachedUrl =
      (await AsyncStorage.getItem('transkrib-backend-url')) ||
      'http://localhost:8000';
  }
  return cachedUrl;
};

export const resetUrlCache = (): void => {
  cachedUrl = null;
};

export interface ResultItem {
  filename: string;
  size_mb: string;
  duration_formatted: string;
  created: string;
}

export const api = {
  async uploadFile(uri: string, name: string) {
    const base = await getBaseUrl();
    const form = new FormData();
    form.append('file', { uri, name, type: 'video/mp4' } as any);
    const res = await fetch(`${base}/api/tasks/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async submitUrl(url: string) {
    const base = await getBaseUrl();
    const res = await fetch(`${base}/api/tasks/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getTaskStatus(taskId: string) {
    const base = await getBaseUrl();
    const res = await fetch(`${base}/api/tasks/${taskId}`);
    return res.json();
  },

  async listResults(): Promise<ResultItem[]> {
    const base = await getBaseUrl();
    const res = await fetch(`${base}/api/results/`);
    if (!res.ok) return [];
    return res.json();
  },

  getDownloadUrl: async (name: string) =>
    `${await getBaseUrl()}/api/results/${name}/download`,

  getStreamUrl: async (name: string) =>
    `${await getBaseUrl()}/api/results/${name}/stream`,

  getWsUrl: async (taskId: string) =>
    `${(await getBaseUrl()).replace(/^http/, 'ws')}/ws/tasks/${taskId}/progress`,
};
