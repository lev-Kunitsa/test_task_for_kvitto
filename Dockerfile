# Общая основа: Python и зависимости приложения
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости отдельным слоем — пересобираются, только когда меняется requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Тестовый образ: + pytest/httpx/ruff и тесты. Запуск: docker compose run --rm --build tests
FROM base AS tests

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pyproject.toml .
COPY app ./app
COPY tests ./tests

CMD ["sh", "-c", "pytest && ruff check . && ruff format --check ."]


# Образ приложения — без тестов и dev-зависимостей.
# Последняя стадия собирается по умолчанию, если target не указан.
FROM base AS app

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
