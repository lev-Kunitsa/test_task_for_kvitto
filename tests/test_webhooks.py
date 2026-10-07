"""Тесты вебхука банка: допустимые и запрещённые переходы статусов платежа."""

import uuid

import pytest
from fastapi.testclient import TestClient


def send_webhook(client: TestClient, payment_id: str, status: str):
    """Отправляет вебхук банка о смене статуса платежа."""
    return client.post("/webhooks/bank", json={"payment_id": payment_id, "status": status})


def get_status(client: TestClient, payment_id: str) -> str:
    """Читает текущий статус платежа через API."""
    return client.get(f"/payments/{payment_id}").json()["status"]


@pytest.mark.parametrize(
    "path",
    [
        ["succeeded"],
        ["failed"],
        ["succeeded", "refunded"],
    ],
)
def test_allowed_transitions(client: TestClient, create_payment, path: list[str]) -> None:
    """Допустимые переходы статуса возвращают 200 {"result": "ok"} и меняют статус.

    pending → succeeded, pending → failed, succeeded → refunded.
    """
    payment_id = create_payment().json()["id"]

    for status in path:
        response = send_webhook(client, payment_id, status)
        assert response.status_code == 200
        assert response.json() == {"result": "ok"}
        assert get_status(client, payment_id) == status


@pytest.mark.parametrize(
    ("path", "forbidden"),
    [
        ([], "refunded"),  # pending -> refunded
        ([], "pending"),  # pending -> pending
        (["succeeded"], "succeeded"),  # повтор того же статуса
        (["succeeded"], "failed"),
        (["failed"], "succeeded"),
        (["succeeded", "refunded"], "succeeded"),
    ],
)
def test_forbidden_transition_is_409_and_status_unchanged(
    client: TestClient, create_payment, path: list[str], forbidden: str
) -> None:
    """Запрещённый переход статуса возвращает 409 {"error": "invalid_transition"}
    и не меняет статус.

    Повтор текущего статуса тоже считается запрещённым переходом — согласованное решение.
    """
    payment_id = create_payment().json()["id"]
    for status in path:
        assert send_webhook(client, payment_id, status).status_code == 200
    status_before = get_status(client, payment_id)

    response = send_webhook(client, payment_id, forbidden)

    assert response.status_code == 409
    assert response.json() == {"error": "invalid_transition"}
    assert get_status(client, payment_id) == status_before


def test_webhook_for_missing_payment_is_404(client: TestClient) -> None:
    """Вебхук по несуществующему платежу возвращает 404."""
    response = send_webhook(client, str(uuid.uuid4()), "succeeded")

    assert response.status_code == 404


def test_webhook_non_uuid_payment_id_is_422(client: TestClient) -> None:
    """payment_id в вебхуке не в формате UUID — 422 (ошибка валидации тела), а не 404."""
    response = send_webhook(client, "1", "succeeded")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "payment_id"]


def test_webhook_unknown_status_is_422(client: TestClient, create_payment) -> None:
    """Неизвестный статус в вебхуке — 422, статус платежа не меняется."""
    payment_id = create_payment().json()["id"]

    response = send_webhook(client, payment_id, "paid")

    assert response.status_code == 422
    assert get_status(client, payment_id) == "pending"
