"""Общие фикстуры тестов: клиент API на чистой in-memory базе и хелперы."""

import os

# Должно выполниться до импорта app: движок создаётся при импорте app.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Payment  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Клиент API на чистой базе: на каждый тест таблицы пересоздаются.

    Таблицы и тарифы создаёт lifespan приложения при входе в TestClient.
    """
    Base.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def payments_count() -> Callable[[], int]:
    """Функция, считающая платежи прямо в базе, — проверка, что дубль не создан."""

    def count() -> int:
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(Payment))

    return count


@pytest.fixture
def tariff_ids(client: TestClient) -> dict[str, int]:
    """Соответствие названия тарифа и его id: {"basic": 1, ...}."""
    return {t["title"]: t["id"] for t in client.get("/tariffs").json()}


@pytest.fixture
def create_payment(client: TestClient, tariff_ids: dict[str, int]):
    """Создаёт платёж; по умолчанию standard картой без промокода."""

    def _create(tariff: str = "standard", headers: dict | None = None, **fields):
        body = {"tariff_id": tariff_ids[tariff], "email": "student@example.com", "method": "card"}
        body.update(fields)
        return client.post("/payments", json=body, headers=headers or {})

    return _create
