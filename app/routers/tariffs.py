from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tariff
from app.schemas import TariffOut

router = APIRouter(tags=["tariffs"])


@router.get("/tariffs", response_model=list[TariffOut])
def list_tariffs(db: Annotated[Session, Depends(get_db)]) -> list[Tariff]:
    return list(db.scalars(select(Tariff).order_by(Tariff.id)))
