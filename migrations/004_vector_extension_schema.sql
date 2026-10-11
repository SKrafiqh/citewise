-- 004_vector_extension_schema.sql — SUPABASE ONLY. Moves pgvector out of the public schema
-- (Supabase security advisor "extension in public"). Do not run on plain Postgres: its default
-- search_path does not include the `extensions` schema.
alter extension vector set schema extensions;
