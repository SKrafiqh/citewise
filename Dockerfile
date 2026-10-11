# Build from the repository root:  docker build -t study-companion .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY prompts prompts
COPY data/derived data/derived
RUN useradd --create-home app && mkdir -p data/uploads .cache && chown -R app /app
USER app

WORKDIR /app/backend
EXPOSE 8000
# Client IPs for rate limiting come from X-Forwarded-For via TRUSTED_PROXY_HOPS (app/api/deps.py)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
