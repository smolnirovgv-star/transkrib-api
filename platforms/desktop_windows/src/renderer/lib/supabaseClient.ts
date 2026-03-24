import { createClient, SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabaseConfigured = !!(url && key && !url.includes('your-project'));

if (!supabaseConfigured) {
  console.info('[Supabase] Не настроен — auth отключён. Укажите VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY в .env');
}

export const supabase: SupabaseClient = supabaseConfigured
  ? createClient(url, key, {
      auth: {
        persistSession: true,
        storageKey: 'transkrib-auth',
        storage: window.localStorage,
        autoRefreshToken: true,
        detectSessionInUrl: false,
      },
    })
  : (null as unknown as SupabaseClient);
