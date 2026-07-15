-- Add posted_date column to jobs table
alter table public.jobs add column if not exists posted_date text default '';

-- Add posted_date to the unique constraint so same job isn't re-added
-- The existing unique(user_id, title, company) constraint stays as-is
