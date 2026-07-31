-- Add per-user Gmail app password for email scanning
alter table public.email_preferences add column if not exists gmail_app_password text default '';

