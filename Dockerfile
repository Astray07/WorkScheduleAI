FROM python:3.13-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY docs/contracts ./docs/contracts
COPY scripts ./scripts
COPY src ./src

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-build-isolation ".[deploy]"

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn work_schedule_ai.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
