-- JobPilot Database Schema for Supabase
-- Run this in the Supabase SQL Editor

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ── Users (extends Supabase auth.users) ──────────────────────────────────
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  email text not null,
  full_name text default '',
  resume_path text default '',
  core_skills jsonb default '[]',
  current_role text default '',
  years_experience int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql security definer;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── Resumes ──────────────────────────────────────────────────────────────
create table public.resumes (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  filename text not null,
  storage_path text not null,
  parsed_name text default '',
  parsed_role text default '',
  parsed_skills jsonb default '[]',
  parsed_experience int default 0,
  is_active boolean default true,
  created_at timestamptz default now()
);

-- ── Jobs ─────────────────────────────────────────────────────────────────
create table public.jobs (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  title text not null,
  company text not null,
  location text default '',
  url text default '',
  description text default '',
  score int default 0,
  score_note text default '',
  salary text default '',
  source text default '',
  status text default 'new' check (status in ('new', 'applied', 'rejected', 'offer')),
  notes text default '',
  found_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(user_id, title, company)
);

-- ── Searches (for rate limiting) ─────────────────────────────────────────
create table public.searches (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  query text not null,
  location text default 'Remote',
  results_count int default 0,
  created_at timestamptz default now()
);

-- ── Indexes ──────────────────────────────────────────────────────────────
create index idx_jobs_user_id on public.jobs(user_id);
create index idx_jobs_status on public.jobs(user_id, status);
create index idx_resumes_user_id on public.resumes(user_id);
create index idx_searches_user_id on public.searches(user_id);
create index idx_searches_created on public.searches(user_id, created_at desc);

-- ── RLS Policies ─────────────────────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.resumes enable row level security;
alter table public.jobs enable row level security;
alter table public.searches enable row level security;

-- Profiles: users can only read/update their own
create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Resumes: users can only access their own
create policy "Users can view own resumes"
  on public.resumes for select
  using (auth.uid() = user_id);

create policy "Users can insert own resumes"
  on public.resumes for insert
  with check (auth.uid() = user_id);

create policy "Users can delete own resumes"
  on public.resumes for delete
  using (auth.uid() = user_id);

-- Jobs: users can only access their own
create policy "Users can view own jobs"
  on public.jobs for select
  using (auth.uid() = user_id);

create policy "Users can insert own jobs"
  on public.jobs for insert
  with check (auth.uid() = user_id);

create policy "Users can update own jobs"
  on public.jobs for update
  using (auth.uid() = user_id);

create policy "Users can delete own jobs"
  on public.jobs for delete
  using (auth.uid() = user_id);

-- Searches: users can only access their own
create policy "Users can view own searches"
  on public.searches for select
  using (auth.uid() = user_id);

create policy "Users can insert own searches"
  on public.searches for insert
  with check (auth.uid() = user_id);

-- ── Storage Buckets ──────────────────────────────────────────────────────
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

-- Storage policy: users can only upload/read their own files
create policy "Users can upload own resumes"
  on storage.objects for insert
  with check (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "Users can read own resumes"
  on storage.objects for select
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

create policy "Users can delete own resumes"
  on storage.objects for delete
  using (
    bucket_id = 'resumes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- ── Email Preferences ────────────────────────────────────────────────────
create table public.email_preferences (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null unique,
  enabled boolean default false,
  frequency text default 'weekly' check (frequency in ('daily', 'weekly', 'biweekly')),
  email text default '',
  last_sent_at timestamptz default null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_email_prefs_user_id on public.email_preferences(user_id);
create index idx_email_prefs_enabled on public.email_preferences(enabled) where enabled = true;

alter table public.email_preferences enable row level security;

create policy "Users can view own email preferences"
  on public.email_preferences for select
  using (auth.uid() = user_id);

create policy "Users can insert own email preferences"
  on public.email_preferences for insert
  with check (auth.uid() = user_id);

create policy "Users can update own email preferences"
  on public.email_preferences for update
  using (auth.uid() = user_id);

-- ── Subscription / Freemium ──────────────────────────────────────────────
create table public.subscriptions (
  id uuid default uuid_generate_v4() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null unique,
  plan text default 'free' check (plan in ('free', 'pro', 'enterprise')),
  searches_today int default 0,
  searches_reset_at date default current_date,
  tracker_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_subscriptions_user_id on public.subscriptions(user_id);

alter table public.subscriptions enable row level security;

create policy "Users can view own subscription"
  on public.subscriptions for select
  using (auth.uid() = user_id);

create policy "Users can insert own subscription"
  on public.subscriptions for insert
  with check (auth.uid() = user_id);

create policy "Users can update own subscription"
  on public.subscriptions for update
  using (auth.uid() = user_id);
