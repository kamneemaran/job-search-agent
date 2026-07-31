-- Add missing email_preferences columns used by the digest API
alter table public.email_preferences add column if not exists batches jsonb default '["all"]'::jsonb;
alter table public.email_preferences add column if not exists posted_date_filter text default 'any';
alter table public.email_preferences add column if not exists day_of_month int default 1;
alter table public.email_preferences add column if not exists sent_history jsonb default '[]'::jsonb;
alter table public.email_preferences add column if not exists webhook_url text default '';
alter table public.email_preferences add column if not exists gmail_label text default '';
alter table public.email_preferences add column if not exists gmail_app_password text default '';
alter table public.email_preferences add column if not exists gmail_configured boolean default false;
