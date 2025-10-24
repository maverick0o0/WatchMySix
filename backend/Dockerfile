# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VERSION=1.8.3

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python - --version $POETRY_VERSION \
    && ln -s "$POETRY_HOME/bin/poetry" /usr/local/bin/poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
