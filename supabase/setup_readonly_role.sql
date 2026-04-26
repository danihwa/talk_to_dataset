-- Run this once in the Supabase SQL editor.
-- Creates a Postgres role that can ONLY read from the public schema.
-- The agent connects with this role's credentials, so a buggy or
-- compromised LLM physically cannot write/delete data.

create role agent_readonly login password 'CHANGE_ME_BEFORE_RUNNING';

grant usage on schema public to agent_readonly;
grant select on all tables in schema public to agent_readonly;
grant select on all sequences in schema public to agent_readonly;

-- Make future tables in `public` automatically readable too.
alter default privileges in schema public
  grant select on tables to agent_readonly;

-- Lets the role read tables that have RLS enabled
-- without writing any policies. For a real multi-tenant app, drop this
-- line and write RLS policies instead.
alter role agent_readonly bypassrls;
