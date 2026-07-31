-- Allow interview/expired/na statuses on the jobs table (email scan + tracker write these)
alter table public.jobs drop constraint if exists jobs_status_check;
alter table public.jobs add constraint jobs_status_check check (status in ('new', 'applied', 'rejected', 'offer', 'interview', 'expired', 'na'));
