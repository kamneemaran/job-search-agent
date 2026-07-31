-- Flag set once a user saves their email scan settings (hides setup UI)
alter table public.email_preferences add column if not exists gmail_configured boolean default false;
