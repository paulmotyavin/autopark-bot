import re
from datetime import date
from decimal import Decimal, InvalidOperation

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


# ---------- поля автомобиля ----------
# Парсеры бросают ValueError с текстом, который можно показать пользователю.

# Латинские буквы, похожие на кириллические, приводим к кириллице (так в госномерах РФ):
# "A123BC77" и "А123ВС77" — один и тот же номер. Escape-последовательности, чтобы
# в исходнике не перепутать латиницу с кириллицей.
_LATIN = "ABEKMHOPCTYX"
_CYRILLIC = "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0423\u0425"
_LATIN_TO_CYRILLIC = str.maketrans(_LATIN, _CYRILLIC)
_PLATE_RE = re.compile("[0-9A-Z\u0410-\u042f\u0401]{4,12}")
_VIN_RE = re.compile("[A-HJ-NPR-Z0-9]{17}")  # в VIN не бывает букв I, O, Q
_DIGITS_RE = re.compile("[0-9]+")
_SPACES_RE = re.compile("[\\s\u00a0]")


def parse_plate(raw: str) -> str:
    plate = re.sub(r"[\s\-]", "", raw.upper()).translate(_LATIN_TO_CYRILLIC)
    if not _PLATE_RE.fullmatch(plate) or not any(ch.isdigit() for ch in plate):
        raise ValueError("Не похоже на госномер. Пример: А123ВС77")
    return plate


def parse_title(raw: str) -> str:
    """Марка или модель: 1-64 символа, лишние пробелы схлопываются."""
    value = " ".join(raw.split())
    if not 1 <= len(value) <= 64:
        raise ValueError("Введите от 1 до 64 символов.")
    return value


def parse_year(raw: str) -> int:
    max_year = date.today().year + 1
    text = raw.strip()
    if not _DIGITS_RE.fullmatch(text) or not 1980 <= int(text) <= max_year:
        raise ValueError(f"Введите год числом от 1980 до {max_year}, например 2020.")
    return int(text)


def parse_km(raw: str) -> int:
    text = _SPACES_RE.sub("", raw)
    if not _DIGITS_RE.fullmatch(text) or int(text) > 2_000_000:
        raise ValueError("Введите пробег целым числом в км, например 120000.")
    return int(text)


def parse_money(raw: str) -> Decimal:
    message = "Введите сумму числом, например 1500000."
    text = _SPACES_RE.sub("", raw).replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(message) from None
    if not value.is_finite() or not 0 <= value < Decimal(10) ** 10:
        raise ValueError(message)
    return value.quantize(Decimal("0.01"))


def parse_vin(raw: str) -> str:
    vin = _SPACES_RE.sub("", raw.upper())
    if not _VIN_RE.fullmatch(vin):
        raise ValueError("VIN — 17 символов: латинские буквы (кроме I, O, Q) и цифры.")
    return vin


def format_km(km: int) -> str:
    return f"{km:,}".replace(",", "\u00a0") + "\u00a0км"


def format_money(amount: Decimal) -> str:
    whole = amount == amount.to_integral_value()
    text = f"{amount:,.0f}" if whole else f"{amount:,.2f}"
    return text.replace(",", "\u00a0") + "\u00a0\u20bd"
