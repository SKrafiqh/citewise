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

See [CLAUDE.md](CLAUDE.md) for architecture, rules and module map, and [docs/SESSION_PROMPTS.md](docs/SESSION_PROMPTS.md) for the build sequence.

## Course material

To be listed with licenses once chosen.

## Related work

[OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) generates interactive lessons from a topic or document. This project differs by grounding every answer and question in the student's own course material with exact source links, and by adapting to the student through a learner model.
