from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import BankWebhook
from app.services import payments as service

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/bank", response_model=None)
def bank_webhook(
    data: BankWebhook, db: Annotated[Session, Depends(get_db)]
) -> dict[str, str] | JSONResponse:
    try:
        service.change_status(db, data.payment_id, data.status)
    except service.PaymentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Платёж не найден"
        ) from None
    except service.InvalidTransitionError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"error": "invalid_transition"}
        )
    return {"result": "ok"}
