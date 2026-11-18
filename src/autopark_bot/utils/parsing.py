import re

_NON_PHONE = re.compile(r"[^\d+]")


def normalize_phone(raw: str) -> str | None:
    """'+7 (900) 123-45-67' -> '+79001234567'. None, если это не похоже на телефон."""
    cleaned = _NON_PHONE.sub("", raw)
    digits = cleaned.lstrip("+")
    if not digits.isdigit() or not 10 <= len(digits) <= 15:
        return None
    return f"+{digits}" if cleaned.startswith("+") else digits


def parse_name_and_phone(args: str | None) -> tuple[str, str | None] | None:
    """'Иван Иванов | +7 900 123-45-67' -> ('Иван Иванов', '+79001234567').

    Телефон необязателен. None — формат неверный (пустое имя, странный телефон).
    """
    if not args:
        return None
    name_part, _, phone_part = args.partition("|")
    name = " ".join(name_part.split())
    if not 2 <= len(name) <= 200:
        return None
    phone: str | None = None
    if phone_part.strip():
        phone = normalize_phone(phone_part)
        if phone is None:
            return None
    return name, phone
