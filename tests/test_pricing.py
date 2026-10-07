"""Юнит-тесты денежной логики: расчёт скидки по промокоду и график рассрочки."""

import pytest

from app.services.pricing import build_schedule, calc_discount


@pytest.mark.parametrize(
    ("price", "promo", "expected"),
    [
        (1990000, None, 0),
        (1990000, "KVITTO10", 199000),
        (990000, "KVITTO10", 99000),
        (2990000, "KVITTO10", 299000),
        # 10% от 1005 коп. = 100.5 -> округляем скидку вверх, в пользу клиента
        (1005, "KVITTO10", 101),
    ],
)
def test_calc_discount(price: int, promo: str | None, expected: int) -> None:
    """Скидка по промокоду считается в целых копейках.

    Без промокода скидка нулевая; KVITTO10 даёт 10% от цены. Если 10% не делятся
    нацело, скидка округляется вверх — в пользу клиента (наше решение, в задании его нет).
    """
    assert calc_discount(price, promo) == expected


def test_schedule_example_from_spec() -> None:
    """График рассрочки совпадает с примером из задания: 1 990 000 коп. на 3 месяца."""
    assert build_schedule(1990000, 3) == [663334, 663333, 663333]


@pytest.mark.parametrize("months", [3, 6, 12])
@pytest.mark.parametrize("amount", [990000, 1990000, 2990000, 1791000, 1000001, 7])
def test_schedule_sum_equals_amount(amount: int, months: int) -> None:
    """Сумма графика рассрочки ровно равна сумме к оплате для 3, 6 и 12 месяцев.

    Дополнительно проверяем правило «лишние копейки — в первые платежи»: график
    не возрастает, а платежи отличаются друг от друга не больше чем на копейку.
    """
    schedule = build_schedule(amount, months)

    assert len(schedule) == months
    assert sum(schedule) == amount
    assert all(isinstance(p, int) for p in schedule)
    assert schedule == sorted(schedule, reverse=True)
    assert schedule[0] - schedule[-1] <= 1
