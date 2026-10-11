-- 005_unique_check_attempt.sql — a tutor check question (no assessment) counts once per student.
create unique index attempts_check_question_uidx
  on attempts (student_id, question_id) where assessment_id is null;
