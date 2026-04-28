-- Migration: add 'telegram_direct' to task_metrics.download_method allowed values
-- Date: 2026-04-28
-- Reason: New Level 0 download path for Telegram CDN URLs (commit a4305fb)
-- Apply manually in Supabase SQL Editor

-- Step 1: Check current constraint definition (run separately to see what's there)
-- SELECT conname, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conname = 'task_metrics_download_method_check';

-- Step 2: Drop existing constraint
ALTER TABLE task_metrics
DROP CONSTRAINT IF EXISTS task_metrics_download_method_check;

-- Step 3: Recreate with telegram_direct + all_failed added
ALTER TABLE task_metrics
ADD CONSTRAINT task_metrics_download_method_check
CHECK (download_method IN (
    'yt_dlp',
    'cobalt',
    'rapidapi',
    'supadata',
    'telegram_direct',
    'all_failed',
    'pytubefix',
    'not_requested'
));

-- Verify
-- SELECT conname, pg_get_constraintdef(oid) 
-- FROM pg_constraint 
-- WHERE conname = 'task_metrics_download_method_check';
