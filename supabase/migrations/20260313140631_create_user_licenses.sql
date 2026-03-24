-- user_licenses: привязка лицензионных ключей к аккаунтам Supabase
CREATE TABLE IF NOT EXISTS public.user_licenses (
  id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id      UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  license_key  TEXT        NOT NULL,
  plan         TEXT        NOT NULL CHECK (plan IN ('BASE', 'STND', 'PREM', 'TRIAL')),
  days         INTEGER     NOT NULL DEFAULT 30,
  activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at   TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, license_key)
);

-- Автоматически вычисляем expires_at при вставке
CREATE OR REPLACE FUNCTION public.set_license_expires_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.expires_at IS NULL THEN
    NEW.expires_at := NEW.activated_at + (NEW.days || ' days')::INTERVAL;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_set_license_expires_at
  BEFORE INSERT ON public.user_licenses
  FOR EACH ROW EXECUTE FUNCTION public.set_license_expires_at();

-- RLS
ALTER TABLE public.user_licenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "select_own" ON public.user_licenses
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "insert_own" ON public.user_licenses
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "update_own" ON public.user_licenses
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "delete_own" ON public.user_licenses
  FOR DELETE USING (auth.uid() = user_id);

-- Индекс для быстрого поиска по user_id
CREATE INDEX IF NOT EXISTS idx_user_licenses_user_id
  ON public.user_licenses (user_id);

-- Представление: активные (не просроченные) лицензии текущего пользователя
CREATE OR REPLACE VIEW public.my_active_licenses AS
  SELECT *
  FROM   public.user_licenses
  WHERE  user_id = auth.uid()
    AND  (expires_at IS NULL OR expires_at > NOW());
