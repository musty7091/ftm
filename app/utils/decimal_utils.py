from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


Q2 = Decimal("0.01")
Q6 = Decimal("0.000001")


class DecimalParseError(ValueError):
    pass


def parse_decimal(value: object, *, scale: Decimal = Q2, field_name: str = "Tutar") -> Decimal:
    if value is None:
        raise DecimalParseError(f"{field_name} boş olamaz.")

    if isinstance(value, Decimal):
        decimal_value = value
    else:
        text_value = str(value).strip()

        if not text_value:
            raise DecimalParseError(f"{field_name} boş olamaz.")

        text_value = text_value.replace(" ", "")

        if "," in text_value and "." in text_value:
            text_value = text_value.replace(".", "").replace(",", ".")
        elif "," in text_value:
            text_value = text_value.replace(",", ".")

        try:
            decimal_value = Decimal(text_value)
        except InvalidOperation as exc:
            raise DecimalParseError(f"{field_name} sayısal olmalıdır. Gelen değer: {value}") from exc

    return decimal_value.quantize(scale, rounding=ROUND_HALF_UP)


def money(value: object, *, field_name: str = "Tutar") -> Decimal:
    return parse_decimal(value, scale=Q2, field_name=field_name)


def rate(value: object, *, field_name: str = "Oran") -> Decimal:
    return parse_decimal(value, scale=Q6, field_name=field_name)