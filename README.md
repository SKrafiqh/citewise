# Grounded Study Companion

An AI study companion that turns lecture videos, a textbook and slide decks into a source-cited knowledge base, then tutors students and runs verified adaptive quizzes driven by a Bayesian Knowledge Tracing learner model. Every answer and question links to the exact page, slide or video second it came from.

Built for Track D of the Multimodal AI Hackathon 2026 (IIT Mandi).

> Status: in development (day 1 of 8). Results, demo video and architecture docs land here before submission.

## Quick start

```bash
cp .env.example .env            # fill in GEMINI_API_KEY, OPENROUTER_API_KEY, DATABASE_URL
psql "$DATABASE_URL" -f migrations/001_init.sql   # or paste it into the Supabase SQL editor
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload   # http://127.0.0.1:8000/health
```

## Repository layout

| Doc | Purpose |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements and success metrics |
| [docs/TRD.md](docs/TRD.md) | Technical design and API contract |
| [docs/EVAL_PLAN.md](docs/EVAL_PLAN.md) | Evaluation protocol |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Development workflow |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log |
| [CLAUDE.md](CLAUDE.md) | Rules for Claude Code |

## Course material

| Source | Content used | License |
|---|---|---|
| [MIT OCW 6.041 Probabilistic Systems Analysis (Fall 2010)](https://ocw.mit.edu/courses/6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/) | Lecture videos 1–3 and their slides | CC BY-NC-SA 4.0 |
| [OpenStax Introductory Statistics 2e](https://openstax.org/details/books/introductory-statistics-2e) | Chapter 3, Probability Topics | CC BY 4.0 |

Run `bash scripts/download_material.sh` to fetch the MIT material; the OpenStax PDF is downloaded by hand (instructions printed by the script).

## Related work

[OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) generates interactive lessons from a topic or document. This project differs by grounding every answer and question in the student's own course material with exact source links, and by adapting to the student through a learner model.
