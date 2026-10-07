-- 001_init.sql — core schema for the grounded study companion.
-- Apply once on a fresh dev database (Supabase SQL editor or psql -f).

create extension if not exists vector;

-- ---------- Knowledge base ----------

create table sources (
  id          text primary key,                 -- e.g. 'lecture_03', 'textbook', 'slides_l2'
  title       text not null,
  modality    text not null check (modality in ('video', 'pdf', 'slide')),
  uri         text not null,                     -- file path or YouTube URL
  license     text,                              -- stated in README
  status      text not null default 'pending',   -- pending | ingesting | ready | failed
  created_at  timestamptz not null default now()
);

create table units (
  id           text primary key,                 -- e.g. 'u_0412'
  source_id    text not null references sources(id) on delete cascade,
  modality     text not null check (modality in ('video', 'pdf', 'slide')),
  locator      jsonb not null,                   -- {"page":87} | {"slide":14} | {"t_start":742,"t_end":808}
  text         text not null,
  figure_desc  text,                             -- vision-model description of figures in this unit
  embedding    vector(768),
  tsv          tsvector generated always as (
                 to_tsvector('english', coalesce(text, '') || ' ' || coalesce(figure_desc, ''))
               ) stored
);
create index units_embedding_idx on units using hnsw (embedding vector_cosine_ops);
create index units_tsv_idx on units using gin (tsv);
create index units_source_idx on units (source_id);

-- Topic -> subtopic -> concept hierarchy (one table, typed by level)
create table concepts (
  id         text primary key,                   -- e.g. 'c_bayes_rule'
  name       text not null,
  level      text not null check (level in ('topic', 'subtopic', 'concept')),
  parent_id  text references concepts(id) on delete cascade,
  summary    text
);

create table concept_prereqs (
  concept_id  text not null references concepts(id) on delete cascade,
  prereq_id   text not null references concepts(id) on delete cascade,
  primary key (concept_id, prereq_id),
  check (concept_id <> prereq_id)
);

create table unit_concepts (
  unit_id     text not null references units(id) on delete cascade,
  concept_id  text not null references concepts(id) on delete cascade,
  confidence  real not null check (confidence between 0 and 1),
  primary key (unit_id, concept_id)
);

-- ---------- Assessment ----------

create table questions (
  id             text primary key,
  qtype          text not null check (qtype in ('mcq', 'short', 'numerical')),
  stem           text not null,
  options        jsonb,                          -- MCQ: [{"key":"A","text":"...","misconception":"..."}]
  answer_key     jsonb not null,                 -- MCQ: "B"; numerical: {"value":..,"tol":..}; short: rubric points
  concept_id     text not null references concepts(id),
  anchor_units   text[] not null,                -- source units the question was generated from
  difficulty     real not null check (difficulty between 0 and 1),
  bloom          text,
  verified       boolean not null default false,
  verify_log     jsonb,                          -- what each checker said
  embedding      vector(768),
  created_at     timestamptz not null default now()
);
create index questions_concept_idx on questions (concept_id);

-- ---------- Learners ----------

create table students (
  id          text primary key,
  name        text,
  exam_date   date,
  is_simulated boolean not null default false,
  profile     jsonb,                             -- intake answers or simulated hidden truth
  created_at  timestamptz not null default now()
);

create table assessments (
  id          text primary key,
  student_id  text not null references students(id) on delete cascade,
  kind        text not null check (kind in ('diagnostic', 'quiz', 'mock_exam', 'check')),
  scope       text[],                            -- concept ids chosen by the student
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  report      jsonb
);

create table attempts (
  id             bigserial primary key,
  assessment_id  text references assessments(id) on delete cascade,
  student_id     text not null references students(id) on delete cascade,
  question_id    text not null references questions(id),
  response       jsonb not null,
  correct        boolean not null,
  score          real not null check (score between 0 and 1),  -- partial credit for short answers
  weight         real not null default 1.0,      -- 0.5 for tutor check questions
  feedback       jsonb,                          -- explanation + cited unit ids
  answered_at    timestamptz not null default now()
);
create index attempts_student_idx on attempts (student_id, answered_at);

-- BKT state + spaced-repetition state per student per concept
create table mastery (
  student_id   text not null references students(id) on delete cascade,
  concept_id   text not null references concepts(id) on delete cascade,
  p_known      real not null check (p_known between 0 and 1),
  stability    real,                             -- days; for forgetting curve
  last_review  timestamptz,
  n_obs        int not null default 0,
  updated_at   timestamptz not null default now(),
  primary key (student_id, concept_id)
);

-- History for mastery charts and the evaluation
create table mastery_log (
  id          bigserial primary key,
  student_id  text not null references students(id) on delete cascade,
  concept_id  text not null references concepts(id) on delete cascade,
  p_before    real not null,
  p_after     real not null,
  source      text not null,                     -- 'quiz' | 'check' | 'diagnostic' | 'intake'
  at          timestamptz not null default now()
);

-- ---------- Tutor chat ----------

create table chat_messages (
  id          bigserial primary key,
  student_id  text not null references students(id) on delete cascade,
  role        text not null check (role in ('user', 'assistant')),
  content     jsonb not null,                    -- assistant: sentences with cited unit ids + outside box
  created_at  timestamptz not null default now()
);
