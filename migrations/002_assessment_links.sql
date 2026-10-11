-- 002_assessment_links.sql — gaps found while building the engine.
-- Apply after 001_init.sql.

-- Which questions an assessment served (needed for "seen" tracking and the report).
create table assessment_questions (
  assessment_id  text not null references assessments(id) on delete cascade,
  question_id    text not null references questions(id),
  position       int  not null,
  primary key (assessment_id, question_id)
);
create index assessment_questions_question_idx on assessment_questions (question_id);

-- Feedback text shown after an answer; ingestion error for failed sources.
alter table questions add column explanation text;
alter table sources   add column error text;

-- Foreign-key / lookup indexes.
create index unit_concepts_concept_idx   on unit_concepts (concept_id);
create index concept_prereqs_prereq_idx  on concept_prereqs (prereq_id);
create index concepts_parent_idx         on concepts (parent_id);
create index attempts_question_idx       on attempts (question_id);
create index attempts_assessment_idx     on attempts (assessment_id);
create index assessments_student_idx     on assessments (student_id);
create index mastery_log_student_idx     on mastery_log (student_id, at);
create index chat_messages_student_idx   on chat_messages (student_id, created_at);
create index questions_verified_idx      on questions (verified);

-- The API connects as the database owner (bypasses RLS). Enabling RLS with no
-- policies blocks the public Supabase REST API (anon / authenticated roles).
alter table sources              enable row level security;
alter table units                enable row level security;
alter table concepts             enable row level security;
alter table concept_prereqs      enable row level security;
alter table unit_concepts        enable row level security;
alter table questions            enable row level security;
alter table students             enable row level security;
alter table assessments          enable row level security;
alter table assessment_questions enable row level security;
alter table attempts             enable row level security;
alter table mastery              enable row level security;
alter table mastery_log          enable row level security;
alter table chat_messages        enable row level security;
