# Development workflow

How work moves from the PRD to a committed, tested module. One loop per module, one module per Claude Code session.

## Document map

| File | Read when |
|---|---|
| `CLAUDE.md` | Claude Code reads it automatically every session; the rules |
| `docs/planning/PRD.md` | What to build and how we know it works (requirement IDs) |
| `docs/planning/TRD.md` | How each part is built; API contract |
| `docs/planning/SESSION_PROMPTS.md` | The exact prompt for each session, in order |
| `docs/planning/EVAL_PLAN.md` | What gets measured and how |
| `docs/planning/TESTSET_FORMAT.md` | Writing `eval/testset.json` |
| `docs/planning/DECISIONS.md` | Why we chose X over Y (append as you go) |
| `docs/architecture.md`, `grounding.md`, `learner_model.md`, `results.md` | Final deliverable docs, filled on Tue 13 Oct |

## The module loop

```
pick next session from SESSION_PROMPTS.md
        │
        ▼
1. PLAN    Claude Code in plan mode → read the plan → fix it → approve
        │
        ▼
2. BUILD   Claude implements + tests (one module only)
        │
        ▼
3. REVIEW  you read every diff (checklist below)
        │
        ▼
4. RUN     pytest -q  +  run it on the real course material
        │
        ▼
5. VERIFY  spot-check outputs by hand (pages, timestamps, answers)
        │
        ▼
6. COMMIT  git commit -m "<module>: <what>"   (PRD IDs in the message)
        │
        ▼
7. LOG     tick the PRD requirement, add any decision to DECISIONS.md
```

If step 4 or 5 fails: stay in the same session, describe what you saw, and fix before committing. Never start the next module on a broken one.

## Review checklist (step 3)

- [ ] Only the files for this module changed
- [ ] Every LLM call goes through `app.llm` (cached)
- [ ] No keys, no hard-coded paths, no print-debugging left
- [ ] Locators are stored exactly (1-based pages and slides, seconds for video)
- [ ] Functions are small and named for what they do; I can explain each one
- [ ] Tests cover the pure logic; LLM calls mocked
- [ ] Your own files (`bkt.py`, `dedup.py`, `metrics.py`) were not rewritten

## Daily rhythm (weekdays, college 8 AM – 3 PM)

| Time | Do |
|---|---|
| Morning commute / breaks | Write test-set questions from the material (`eval/testset.json`) |
| 4:00 – 4:15 PM | Read yesterday's notes; pick today's sessions |
| 4:15 – 8:00 PM | Module loops (usually 2 sessions) |
| 8:00 – 9:30 PM | Your own code (BKT, dedup, metrics), manual checks |
| 9:30 – 10:00 PM | Commit, push, update PRD checkboxes, note tomorrow's first step |

Sunday 11 Oct is the one full day: learner model + frontend.

## Git conventions

- Branch: work on `main` (solo, short project); tag `v0.1-demo` before recording.
- Commit message: `ingest: PDF pages with figure descriptions (KB-1, KB-2, KB-5)`.
- Push at the end of each day. Never commit `.env` or `data/raw/`.

## Claude Code habits

- Start every session with: "Read CLAUDE.md and docs/planning/TRD.md section X before planning."
- Use plan mode for anything touching more than one file.
- When context gets long, finish the module, commit, and start a fresh session rather than continuing.
- Use `/code-review` (ECC) after each module if installed.
- Ask "explain this function" for anything you could not explain to a judge.

## Definition of done (whole project)

- [ ] All P0 rows in PRD §6 ticked
- [ ] `docs/results.md` contains real numbers with n and ablations
- [ ] Public URL works from a phone
- [ ] Demo video uploaded (3–10 min) and linked in README
- [ ] Submitted on Unstop before 11 PM Wed 14 Oct
