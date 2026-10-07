"""Тесты API тарифов и платежей: создание, промокод, рассрочка, валидация,
идемпотентность и получение платежа."""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Payment


def test_tariffs_seeded(client: TestClient) -> None:
    """GET /tariffs возвращает три тарифа, созданных при старте, с ценами в копейках."""
    response = client.get("/tariffs")

    assert response.status_code == 200
    assert [(t["title"], t["price"]) for t in response.json()] == [
        ("basic", 990000),
        ("standard", 1990000),
        ("premium", 2990000),
    ]
    assert all(isinstance(t["id"], int) for t in response.json())


def test_create_payment_without_promo(create_payment, tariff_ids) -> None:
    """Создание платежа без промокода: 201, статус pending, полная цена тарифа.

    Заодно проверяем формат ответа: id — UUID, created_at — с таймзоной.
    """
    response = create_payment()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["tariff_id"] == tariff_ids["standard"]
    assert body["amount"] == 1990000
    assert body["discount"] == 0
    assert body["method"] == "card"
    assert body["installment_months"] is None
    assert body["schedule"] is None
    assert body["email"] == "student@example.com"
    uuid.UUID(body["id"])
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


@pytest.mark.parametrize("promo", ["KVITTO10", "kvitto10", "KvItTo10", "  kvitto10  "])
def test_create_payment_with_promo(create_payment, promo: str) -> None:
    """Промокод KVITTO10 даёт −10% независимо от регистра и пробелов по краям."""
    response = create_payment(promo_code=promo)

    assert response.status_code == 201
    assert response.json()["amount"] == 1791000
    assert response.json()["discount"] == 199000


@pytest.mark.parametrize("promo", ["", "   "])
def test_blank_promo_means_no_promo(create_payment, promo: str) -> None:
    """Пустой или «пробельный» промокод считается отсутствием промокода, а не ошибкой 422."""
    response = create_payment(promo_code=promo)

    assert response.status_code == 201
    assert response.json()["amount"] == 1990000
    assert response.json()["discount"] == 0


def test_unknown_promo_is_422(create_payment, payments_count) -> None:
    """Неизвестный промокод — 422 с указанием на поле promo_code; платёж не создаётся."""
    response = create_payment(promo_code="KVITTO50")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "promo_code"]
    assert payments_count() == 0


@pytest.mark.parametrize("months", [3, 6, 12])
@pytest.mark.parametrize("promo", [None, "kvitto10"])
def test_installment_schedule_sum_equals_amount(create_payment, months: int, promo) -> None:
    """Рассрочка через API: сумма графика равна сумме к оплате для 3, 6 и 12 месяцев,
    в том числе после скидки по промокоду."""
    response = create_payment(method="installment", installment_months=months, promo_code=promo)

    assert response.status_code == 201
    body = response.json()
    assert body["installment_months"] == months
    assert len(body["schedule"]) == months
    assert sum(body["schedule"]) == body["amount"]


def test_installment_schedule_example_from_spec(create_payment) -> None:
    """Рассрочка standard на 3 месяца через API даёт график из примера в задании."""
    response = create_payment(method="installment", installment_months=3)

    assert response.json()["schedule"] == [663334, 663333, 663333]


@pytest.mark.parametrize(
    "fields",
    [
        {"method": "installment"},  # нет срока рассрочки
        {"method": "installment", "installment_months": 4},  # недопустимый срок
        {"method": "card", "installment_months": 3},  # срок без рассрочки
        {"method": "cash"},
        {"email": "not-an-email"},
    ],
)
def test_invalid_body_is_422(create_payment, payments_count, fields: dict) -> None:
    """Некорректное тело запроса — 422, платёж не создаётся.

    Рассрочка без срока или с недопустимым сроком, срок при оплате картой,
    неизвестный способ оплаты, невалидный email.
    """
    response = create_payment(**fields)

    assert response.status_code == 422
    assert payments_count() == 0


def test_unknown_tariff_is_422(client: TestClient, payments_count) -> None:
    """Несуществующий тариф — 422 с указанием на поле tariff_id; платёж не создаётся.

    422, а не 404: ошибка в теле запроса, а не в URL — так же, как с неизвестным промокодом.
    """
    response = client.post(
        "/payments", json={"tariff_id": 999, "email": "a@example.com", "method": "card"}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "tariff_id"]
    assert payments_count() == 0


def test_same_idempotency_key_returns_same_payment(create_payment, payments_count) -> None:
    """Повтор с тем же Idempotency-Key возвращает тот же платёж с кодом 200 и не создаёт дубль."""
    headers = {"Idempotency-Key": "order-42"}

    first = create_payment(headers=headers)
    second = create_payment(headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert payments_count() == 1


def test_different_idempotency_keys_create_different_payments(
    create_payment, payments_count
) -> None:
    """Запросы с разными Idempotency-Key создают разные платежи."""
    first = create_payment(headers={"Idempotency-Key": "a"})
    second = create_payment(headers={"Idempotency-Key": "b"})

    assert first.json()["id"] != second.json()["id"]
    assert payments_count() == 2


def test_without_idempotency_key_each_request_creates_payment(
    create_payment, payments_count
) -> None:
    """Без Idempotency-Key каждый запрос создаёт новый платёж — заголовок необязателен."""
    create_payment()
    create_payment()

    assert payments_count() == 2


@pytest.mark.parametrize("key", ["", "   "])
def test_blank_idempotency_key_means_no_key(create_payment, payments_count, key: str) -> None:
    """Пустой или «пробельный» Idempotency-Key считается отсутствием ключа.

    Иначе пустая строка сохранялась бы как настоящий ключ, и все запросы с пустым
    заголовком схлопнулись бы в один платёж. В базе ключ хранится как NULL.
    """
    first = create_payment(headers={"Idempotency-Key": key})
    second = create_payment(headers={"Idempotency-Key": key})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert payments_count() == 2
    with SessionLocal() as db:
        keys = db.scalars(select(Payment.idempotency_key)).all()
    assert keys == [None, None]


def test_get_payment(client: TestClient, create_payment) -> None:
    """GET /payments/{id} возвращает платёж в том же виде, в каком он был создан."""
    created = create_payment(promo_code="kvitto10").json()

    response = client.get(f"/payments/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_payment_is_404(client: TestClient) -> None:
    """Запрос несуществующего платежа возвращает 404."""
    response = client.get(f"/payments/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.parametrize("payment_id", ["1", "not-a-uuid"])
def test_get_payment_with_non_uuid_id_is_422(client: TestClient, payment_id: str) -> None:
    """id платежа не в формате UUID — 422, а не 404.

    Задокументированное решение: id — UUID, FastAPI валидирует тип параметра пути,
    а ошибки валидации по заданию — стандартный 422.
    """
    response = client.get(f"/payments/{payment_id}")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "payment_id"]
