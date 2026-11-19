from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    DRIVER = "driver"


STAFF_ROLES = frozenset({Role.OWNER, Role.ADMIN})

ROLE_TITLES: dict[Role, str] = {
    Role.OWNER: "владелец",
    Role.ADMIN: "администратор",
    Role.DRIVER: "водитель",
}


class VehicleStatus(StrEnum):
    FREE = "free"  # свободна, можно сдавать
    RENTED = "rented"  # есть активная аренда
    REPAIR = "repair"  # на ремонте
    ARCHIVED = "archived"  # списана, в списках не показываем (но история остаётся)


class DriverStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RentalStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class RatePeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


VEHICLE_STATUS_TITLES: dict[VehicleStatus, str] = {
    VehicleStatus.FREE: "🟢 свободна",
    VehicleStatus.RENTED: "🔵 в аренде",
    VehicleStatus.REPAIR: "🔧 на ремонте",
    VehicleStatus.ARCHIVED: "🗄 в архиве",
}


RATE_PERIOD_TITLES: dict[RatePeriod, str] = {
    RatePeriod.DAILY: "сутки",
    RatePeriod.WEEKLY: "неделя",
    RatePeriod.MONTHLY: "месяц",
}
