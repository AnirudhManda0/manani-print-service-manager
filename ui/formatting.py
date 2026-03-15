from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.01")


def to_money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def format_currency(currency: str, value: object) -> str:
    code = (currency or "INR").strip().upper() or "INR"
    amount = to_money(value)
    return f"{code} {amount:.2f}"
