import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Payment, PaymentMethod, PaymentStatus, Tariff
from app.schemas import PaymentCreate
from app.services.pricing import build_schedule, calc_discount

ALLOWED_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.PENDING: {PaymentStatus.SUCCEEDED, PaymentStatus.FAILED},
    PaymentStatus.SUCCEEDED: {PaymentStatus.REFUNDED},
}


class TariffNotFoundError(Exception):
    pass


class PaymentNotFoundError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


def get_payment_by_key(db: Session, idempotency_key: str) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))


def create_payment(
    db: Session, data: PaymentCreate, idempotency_key: str | None
) -> tuple[Payment, bool]:
    """Создаёт платёж. Возвращает (платёж, создан_ли_новый).

    Если платёж с таким Idempotency-Key уже есть — возвращает его, второй не создаёт.
    """
    if idempotency_key is not None:
        existing = get_payment_by_key(db, idempotency_key)
        if existing is not None:
            return existing, False

    tariff = db.get(Tariff, data.tariff_id)
    if tariff is None:
        raise TariffNotFoundError

    discount = calc_discount(tariff.price, data.promo_code)
    amount = tariff.price - discount
    schedule = None
    if data.method == PaymentMethod.INSTALLMENT:
        schedule = build_schedule(amount, data.installment_months)

    payment = Payment(
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=data.method,
        installment_months=data.installment_months,
        schedule=schedule,
        email=data.email,
        idempotency_key=idempotency_key,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        # Гонка: параллельный запрос с тем же ключом успел вставить платёж раньше нас
        db.rollback()
        if idempotency_key is None:
            raise
        existing = get_payment_by_key(db, idempotency_key)
        if existing is None:
            raise
        return existing, False
    return payment, True


def get_payment(db: Session, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise PaymentNotFoundError
    return payment


def list_payments(
    db: Session,
    email: str | None = None,
    status: PaymentStatus | None = None,
) -> list[Payment]:
    """Платежи с фильтрами, новые сначала. Email сравнивается без учёта регистра."""
    query = select(Payment).order_by(Payment.created_at.desc(), Payment.id)
    if email is not None:
        query = query.where(func.lower(Payment.email) == email.lower())
    if status is not None:
        query = query.where(Payment.status == status)
    return list(db.scalars(query))


def change_status(db: Session, payment_id: uuid.UUID, new_status: PaymentStatus) -> None:
    payment = get_payment(db, payment_id)
    current = payment.status
    if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError

    # Условный UPDATE: меняем статус, только если он всё ещё тот, что мы проверили.
    # Иначе два параллельных вебхука могли бы оба пройти проверку.
    result = db.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == current)
        .values(status=new_status)
    )
    if result.rowcount == 0:
        db.rollback()
        raise InvalidTransitionError
    db.commit()
