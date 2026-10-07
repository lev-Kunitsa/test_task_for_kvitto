import uuid
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.models import PaymentMethod, PaymentStatus
from app.services.pricing import PROMO_CODES


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: int


class PaymentCreate(BaseModel):
    tariff_id: int
    email: EmailStr
    method: PaymentMethod
    installment_months: Literal[3, 6, 12] | None = None
    promo_code: str | None = None

    @field_validator("promo_code")
    @classmethod
    def normalize_promo_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            return None  # пустая или «пробельная» строка = промокода нет
        if value not in PROMO_CODES:
            raise ValueError("Неизвестный промокод")
        return value

    @model_validator(mode="after")
    def check_installment(self) -> Self:
        if self.method == PaymentMethod.INSTALLMENT and self.installment_months is None:
            raise ValueError("Для рассрочки обязателен installment_months")
        if self.method != PaymentMethod.INSTALLMENT and self.installment_months is not None:
            raise ValueError("installment_months допустим только для рассрочки")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: PaymentStatus
    tariff_id: int
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        # SQLite не хранит таймзону и возвращает naive datetime; пишем мы всегда UTC
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class BankWebhook(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
