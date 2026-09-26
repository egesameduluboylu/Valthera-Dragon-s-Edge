-- Just enough of Supabase for running the migrations on a plain local PostgreSQL:
-- the anon/authenticated roles and auth.uid(), which reads the caller's id from the
-- request.jwt.claim.sub setting like PostgREST does.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key);
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;
grant usage on schema auth to anon, authenticated;
grant usage on schema public to anon, authenticated;
grant select on all tables in schema public to anon, authenticated;
alter default privileges in schema public grant select on tables to anon, authenticated;
