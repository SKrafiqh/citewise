"""FastAPI entry point."""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import learning, library, tutor
from app.assess.service import AlreadyAnswered, NotFound
from app.config import get_settings
from app.db import close_pool, connect
from app.llm.jsonutil import LLMOutputError
from app.llm.retry import RETRYABLE_STATUS

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    yield
    close_pool()


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Grounded Study Companion", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )
    for router in (library.router, tutor.router, learning.router):
        app.include_router(router)
    app.mount("/assets", StaticFiles(directory=settings.derived_dir, check_dir=False), name="assets")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        with connect() as conn:
            conn.execute("select 1")
        return {"status": "ready"}

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return _error(404, f"{exc} not found")

    @app.exception_handler(AlreadyAnswered)
    async def already_answered(_: Request, __: AlreadyAnswered) -> JSONResponse:
        return _error(409, "This question was already answered.")

    @app.exception_handler(LLMOutputError)
    async def bad_model_output(_: Request, exc: LLMOutputError) -> JSONResponse:
        log.error("unusable model output: %s", exc)
        return _error(502, "The language model returned an unusable answer; please retry.")

    @app.exception_handler(ValueError)
    async def bad_value(_: Request, exc: ValueError) -> JSONResponse:
        return _error(422, str(exc))

    @app.exception_handler(NotImplementedError)
    async def not_implemented(_: Request, exc: NotImplementedError) -> JSONResponse:
        return _error(501, f"Not implemented yet: {exc}")

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")  # details stay in the server log
        upstream = isinstance(exc, httpx.HTTPError) or getattr(exc, "code", None) in RETRYABLE_STATUS
        return _error(502, "The language model service failed; please retry.") if upstream else _error(500, "Internal server error.")

    return app


app = create_app()
