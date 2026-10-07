"""FastAPI entry point. Routers are added module by module."""
from fastapi import FastAPI

app = FastAPI(title="Grounded Study Companion", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
