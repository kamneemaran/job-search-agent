-- Add google service account columns to profiles table
alter table public.profiles add column if not exists google_sa_json text default '';
alter table public.profiles add column if not exists google_sa_dismissed boolean default false;

