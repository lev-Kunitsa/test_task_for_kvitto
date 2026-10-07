import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentOut
from app.services import payments as service

router = APIRouter(tags=["payments"])


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    data: PaymentCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(max_length=255)] = None,
) -> Payment:
    # Пустой заголовок = ключа нет, иначе все такие запросы схлопнулись бы в один платёж
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip() or None
    try:
        payment, created = service.create_payment(db, data, idempotency_key)
    except service.TariffNotFoundError:
        # Отдаём в стандартном формате ошибок валидации FastAPI
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "tariff_id"),
                    "msg": "Тариф не найден",
                    "input": data.tariff_id,
                }
            ]
        ) from None
    if not created:
        response.status_code = status.HTTP_200_OK
    return payment


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(
    db: Annotated[Session, Depends(get_db)],
    email: Annotated[str | None, Query(max_length=320)] = None,
    status_: Annotated[PaymentStatus | None, Query(alias="status")] = None,
) -> list[Payment]:
    # status_ — чтобы не перекрыть импортированный модуль fastapi.status
    if email is not None:
        email = email.strip() or None
    return service.list_payments(db, email=email, status=status_)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> Payment:
    try:
        return service.get_payment(db, payment_id)
    except service.PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден"
        ) from None
