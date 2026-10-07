import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _str_enum(enum_cls: type[StrEnum]) -> Enum:
    # храним значения ("pending"), а не имена членов ("PENDING"), без нативного ENUM в БД
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda cls: [member.value for member in cls],
    )


class PaymentMethod(StrEnum):
    CARD = "card"
    SBP = "sbp"
    INSTALLMENT = "installment"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50), unique=True)
    price: Mapped[int]  # копейки


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[PaymentStatus] = mapped_column(
        _str_enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"))
    # amount — итог к оплате, discount — размер скидки; оба в копейках
    amount: Mapped[int]
    discount: Mapped[int]
    method: Mapped[PaymentMethod] = mapped_column(_str_enum(PaymentMethod))
    installment_months: Mapped[int | None]
    schedule: Mapped[list[int] | None] = mapped_column(JSON)
    email: Mapped[str] = mapped_column(String(320))
    # unique: два параллельных запроса с одним ключом не создадут два платежа
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
