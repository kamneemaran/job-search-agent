-- Track the last email label scan time per user so the dashboard's
-- "Scan Email & Sync" button only checks emails after that date (incremental),
-- instead of always doing a full 90-day scan.
alter table public.email_preferences add column if not exists last_email_scan_at timestamptz default null;
