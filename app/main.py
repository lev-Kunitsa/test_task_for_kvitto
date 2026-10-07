from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Tariff
from app.routers import payments, tariffs, webhooks

# Цены в копейках
DEFAULT_TARIFFS: dict[str, int] = {
    "basic": 990000,
    "standard": 1990000,
    "premium": 2990000,
}


def init_db() -> None:
    """Создаёт таблицы и тарифы, если их ещё нет. Безопасно вызывать повторно."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = set(db.scalars(select(Tariff.title)))
        for title, price in DEFAULT_TARIFFS.items():
            if title not in existing:
                db.add(Tariff(title=title, price=price))
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Kvitto Payments", lifespan=lifespan)
app.include_router(tariffs.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
