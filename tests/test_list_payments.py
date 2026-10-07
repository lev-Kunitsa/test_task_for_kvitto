"""Тесты списка платежей GET /payments с фильтрами по email и status."""

from fastapi.testclient import TestClient


def ids(response) -> set[str]:
    """Множество id платежей из ответа со списком."""
    return {p["id"] for p in response.json()}


def test_list_without_filters_returns_all(client: TestClient, create_payment) -> None:
    """Без фильтров возвращаются все платежи."""
    created = {create_payment().json()["id"] for _ in range(3)}

    response = client.get("/payments")

    assert response.status_code == 200
    assert ids(response) == created


def test_filter_by_email_case_insensitive(client: TestClient, create_payment) -> None:
    """Фильтр по email возвращает только платежи этого email, без учёта регистра."""
    alice = create_payment(email="alice@example.com").json()["id"]
    create_payment(email="bob@example.com")

    response = client.get("/payments", params={"email": "ALICE@example.com"})

    assert response.status_code == 200
    assert ids(response) == {alice}


def test_filter_by_status(client: TestClient, create_payment) -> None:
    """Фильтр по статусу возвращает только платежи с этим статусом."""
    paid = create_payment().json()["id"]
    create_payment()
    client.post("/webhooks/bank", json={"payment_id": paid, "status": "succeeded"})

    response = client.get("/payments", params={"status": "succeeded"})

    assert ids(response) == {paid}
    assert all(p["status"] == "succeeded" for p in response.json())


def test_filter_by_email_and_status(client: TestClient, create_payment) -> None:
    """Фильтры по email и статусу применяются одновременно (логическое И)."""
    target = create_payment(email="alice@example.com").json()["id"]
    other_alice = create_payment(email="alice@example.com").json()["id"]
    bob = create_payment(email="bob@example.com").json()["id"]
    for payment_id in (target, bob):
        client.post("/webhooks/bank", json={"payment_id": payment_id, "status": "failed"})

    response = client.get("/payments", params={"email": "alice@example.com", "status": "failed"})

    assert ids(response) == {target}
    assert other_alice not in ids(response)


def test_no_matches_returns_empty_list(client: TestClient, create_payment) -> None:
    """Если под фильтры ничего не подходит — 200 и пустой список, а не 404."""
    create_payment()

    response = client.get("/payments", params={"email": "nobody@example.com"})

    assert response.status_code == 200
    assert response.json() == []


def test_returns_all_matches_without_truncation(client: TestClient, create_payment) -> None:
    """Возвращаются все подходящие платежи, список не обрезается.

    Пагинации нет намеренно: ограничение по умолчанию молча теряло бы часть платежей.
    """
    created = {create_payment().json()["id"] for _ in range(60)}

    response = client.get("/payments", params={"email": "student@example.com"})

    assert ids(response) == created


def test_unknown_status_filter_is_422(client: TestClient) -> None:
    """Неизвестный статус в фильтре — 422."""
    response = client.get("/payments", params={"status": "paid"})

    assert response.status_code == 422
