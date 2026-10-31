# Hoshiyar on Fly.io: one process, Python 3.12, dependencies from uv.lock.
# The laptop-mic extra (pyaudio) is in the lockfile, so the builder needs PortAudio headers; the runtime
# image only carries the shared library. Nothing on the server ever imports it.

FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends build-essential portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libportaudio2 tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 TZ=Asia/Kolkata \
    ROSTER_FILE=/data/drivers.json SCHEDULE_FILE=/data/schedule.json \
    CALLS_FILE=/data/calls.jsonl TRIALS_FILE=/data/trials.json
RUN mkdir -p /data
EXPOSE 7860
CMD ["python", "-m", "hoshiyar.server"]
