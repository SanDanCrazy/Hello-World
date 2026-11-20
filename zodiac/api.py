"""Public library API: :func:`get_zodiac` and :class:`ZodiacResult`."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from . import calendar_data as _data
from .converter import LunarDate, lunar_to_solar, solar_to_lunar
from .errors import InvalidDateError, OutOfRangeError
from .signs import get_sign

VALID_CALENDARS = ("solar", "lunar")


@dataclass(frozen=True)
class ZodiacResult:
    """Immutable result of a zodiac lookup."""

    sign_zh: str
    sign_en: str
    solar_date: date
    lunar_year: int
    lunar_month: int
    lunar_day: int
    is_leap_month: bool
    lunar_text: str
    input_calendar: str

    def to_dict(self) -> dict:
        """Return a JSON-friendly dict (``solar_date`` as ``YYYY-MM-DD``)."""
        data = asdict(self)
        data["solar_date"] = self.solar_date.isoformat()
        return data


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidDateError("%s=%r 必须是整数" % (field, value))
    return value


def _to_solar(year: int, month: int, day: int) -> date:
    _require_int(year, "year")
    _require_int(month, "month")
    _require_int(day, "day")
    if not 1 <= month <= 12:
        raise InvalidDateError("month=%d 超出 1..12" % month)
    if not 1 <= day <= 31:
        raise InvalidDateError("day=%d 超出 1..31" % day)
    try:
        return date(year, month, day)
    except ValueError:
        raise InvalidDateError("公历日期 %04d-%02d-%02d 不存在" % (year, month, day))


def _build_result(solar: date, lunar: LunarDate, input_calendar: str) -> ZodiacResult:
    sign_zh, sign_en = get_sign(solar)
    return ZodiacResult(
        sign_zh=sign_zh,
        sign_en=sign_en,
        solar_date=solar,
        lunar_year=lunar.year,
        lunar_month=lunar.month,
        lunar_day=lunar.day,
        is_leap_month=lunar.is_leap_month,
        lunar_text=lunar.text,
        input_calendar=input_calendar,
    )


def get_zodiac(
    year: int,
    month: int,
    day: int,
    *,
    calendar: str = "solar",
    is_leap_month: bool = False,
) -> ZodiacResult:
    """Return the zodiac sign for a solar or lunar birthday.

    ``calendar`` accepts only ``"solar"`` or ``"lunar"``.  When ``calendar``
    is ``"solar"`` the ``is_leap_month`` flag is rejected.
    """
    if calendar not in VALID_CALENDARS:
        raise ValueError("calendar=%r 只接受 'solar' 或 'lunar'" % (calendar,))

    if calendar == "solar":
        if is_leap_month:
            raise InvalidDateError("公历日期不支持 is_leap_month=True")
        solar = _to_solar(year, month, day)
        lunar = solar_to_lunar(solar)
    else:
        _require_int(year, "year")
        if not _data.LUNAR_MIN_YEAR <= year <= _data.LUNAR_MAX_INPUT_YEAR:
            raise OutOfRangeError(
                "农历年份 %d 超出支持范围 %d..%d"
                % (year, _data.LUNAR_MIN_YEAR, _data.LUNAR_MAX_INPUT_YEAR)
            )
        solar = lunar_to_solar(year, month, day, is_leap_month)
        lunar = solar_to_lunar(solar)

    return _build_result(solar, lunar, calendar)