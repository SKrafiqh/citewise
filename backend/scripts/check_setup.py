"""Verify .env: one tiny Gemini call, one embedding (768 dims), one OpenRouter call, the database.

    cd backend && python scripts/check_setup.py

Prints PASS/FAIL per check. Never prints a key or the database URL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402

EXPECTED_TABLES = {"sources", "units", "concepts", "questions", "students", "attempts", "mastery", "assessment_questions"}


def gemini_generate() -> str:
    from app.llm import generate

    return f"model {get_settings().gemini_model} replied {generate('Reply with the single word: ok', temperature=0)[:20]!r}"


def gemini_embed() -> str:
    from app.llm import embed

    dims = len(embed(["setup check"])[0])
    if dims != get_settings().embed_dim:
        raise ValueError(f"got {dims} dimensions, expected {get_settings().embed_dim}")
    return f"{dims} dimensions"


def openrouter() -> str:
    from app.llm import verify_chat

    return f"model {get_settings().openrouter_model} replied {verify_chat('Reply with the single word: ok')[:20]!r}"


def database() -> str:
    from app.db import connect

    with connect() as conn:
        tables = {r["table_name"] for r in conn.execute("select table_name from information_schema.tables where table_schema = 'public'").fetchall()}
        vector = conn.execute("select 1 from pg_extension where extname = 'vector'").fetchone()
    missing = EXPECTED_TABLES - tables
    if missing or not vector:
        raise ValueError(f"missing tables {sorted(missing)} / pgvector {'present' if vector else 'absent'}: apply the migrations")
    return f"{len(tables)} tables, pgvector enabled"


def main() -> int:
    settings = get_settings()
    problems = [name for name, value in (("GEMINI_API_KEY", settings.gemini_api_key), ("OPENROUTER_API_KEY", settings.openrouter_api_key),
                                         ("DATABASE_URL", settings.database_url)) if not value]
    if problems:
        print(f"FAIL  .env is missing: {', '.join(problems)}")
        return 1
    failed = 0
    for name, check in (("gemini generate", gemini_generate), ("gemini embed", gemini_embed), ("openrouter", openrouter), ("database", database)):
        try:
            print(f"PASS  {name}: {check()}")
        except Exception as exc:  # report the class and a short message only, never request details
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {str(exc)[:200]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
