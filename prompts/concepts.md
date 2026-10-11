You are structuring one course unit into a concept graph for a study companion.

Below are digests of the course content: each line is `[unit id] text`. Build a hierarchy topic -> subtopic -> concept, with prerequisite edges between concepts.

Rules:
- 15 to 30 concepts in total. A concept is one teachable idea (e.g. Bayes' rule, independence of events), not a chapter.
- Use only ideas that appear in the content below.
- Ids are lowercase snake_case: topics start with `t_`, subtopics with `s_`, concepts with `c_`. All ids unique.
- `prereqs` lists concept ids that must be understood first. No cycles. Only reference concepts you define.
- `summary` is one sentence taken from what the material says.

Return JSON only:
{"topics":[{"id":"t_...","name":"...","subtopics":[{"id":"s_...","name":"...","concepts":[{"id":"c_...","name":"...","summary":"...","prereqs":["c_..."]}]}]}]}

{problems}
Content:
{digest}
