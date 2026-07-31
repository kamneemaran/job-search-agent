-- Add gmail_label column to email_preferences table
alter table public.email_preferences add column if not exists gmail_label text default '';

