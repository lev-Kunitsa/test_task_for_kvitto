"""Денежная логика. Все суммы — целые копейки, float не используется нигде."""

# Промокод -> скидка в процентах. Ключи в верхнем регистре, ввод нормализуется в схеме.
PROMO_CODES: dict[str, int] = {"KVITTO10": 10}


def calc_discount(price: int, promo_code: str | None) -> int:
    """Размер скидки в копейках. Округляем вверх — в пользу клиента."""
    if promo_code is None:
        return 0
    percent = PROMO_CODES[promo_code]
    # ceil(price * percent / 100) в целых числах: -(-a // b)
    return -(-price * percent // 100)


def build_schedule(amount: int, months: int) -> list[int]:
    """Делит сумму на платежи; остаток по копейке раздаётся первым платежам.

    >>> build_schedule(1990000, 3)
    [663334, 663333, 663333]
    """
    base, remainder = divmod(amount, months)
    return [base + 1] * remainder + [base] * (months - remainder)
