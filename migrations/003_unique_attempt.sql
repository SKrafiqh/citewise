-- 003_unique_attempt.sql — one attempt per question per assessment (blocks double-submit
-- from updating mastery twice).
create unique index attempts_assessment_question_uidx
  on attempts (assessment_id, question_id) where assessment_id is not null;
