"""Lunar <-> Gregorian date conversion (date granularity only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import calendar_data as _data
from .errors import InvalidDateError, OutOfRangeError

SOLAR_MIN_DATE = _data.LUNAR_BASE
SOLAR_MAX_DATE = date(2100, 12, 31)

_YEAR_DIGITS = "〇一二三四五六七八九"
_MONTH_NAMES = (
    "",
    "正月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "冬月",
    "腊月",
)
_DAY_NAMES = (
    "",
    "初一",
    "初二",
    "初三",
    "初四",
    "初五",
    "初六",
    "初七",
    "初八",
    "初九",
    "初十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
    "廿一",
    "廿二",
    "廿三",
    "廿四",
    "廿五",
    "廿六",
    "廿七",
    "廿八",
    "廿九",
    "三十",
)


@dataclass(frozen=True)
class LunarDate:
    """A date on the Chinese lunar calendar."""

    year: int
    month: int
    day: int
    is_leap_month: bool
    text: str


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidDateError("%s=%r 必须是整数" % (field, value))
    return value


def _format_lunar_year(year: int) -> str:
    return "".join(_YEAR_DIGITS[int(ch)] for ch in str(year))


def lunar_text(year: int, month: int, day: int, is_leap_month: bool) -> str:
    """Build a human readable lunar date such as ``农历二〇二四年正月初一``."""
    prefix = "闰" if is_leap_month else ""
    return "农历%s年%s%s%s" % (
        _format_lunar_year(year),
        prefix,
        _MONTH_NAMES[month],
        _DAY_NAMES[day],
    )


def _validate_lunar(y: int, m: int, d: int, is_leap: bool) -> None:
    _require_int(y, "year")
    _require_int(m, "month")
    _require_int(d, "day")
    if not isinstance(is_leap, bool):
        raise InvalidDateError("is_leap_month=%r 必须是布尔值" % (is_leap,))
    if not 1 <= m <= 12:
        raise InvalidDateError("month=%d 超出 1..12" % m)
    if not 1 <= d <= 30:
        raise InvalidDateError("day=%d 超出 1..30" % d)
    if not _data.LUNAR_MIN_YEAR <= y <= _data.LUNAR_TABLE_MAX_YEAR:
        raise OutOfRangeError(
            "农历年份 %d 超出数据表范围 %d..%d"
            % (y, _data.LUNAR_MIN_YEAR, _data.LUNAR_TABLE_MAX_YEAR)
        )
    leap = _data.leap_month(y)
    if is_leap and leap != m:
        if leap == 0:
            raise InvalidDateError("农历 %d 年不存在闰月" % y)
        raise InvalidDateError("农历 %d 年不存在闰%d月" % (y, m))
    if is_leap:
        month_len = _data.leap_days(y)
    else:
        month_len = _data.month_days(y, m)
    if d > month_len:
        raise InvalidDateError(
            "农历 %d 年%s%d月只有 %d 天，不存在第 %d 天"
            % (y, "闰" if is_leap else "", m, month_len, d)
        )


def _validate_solar(d: date) -> None:
    if isinstance(d, bool) or not isinstance(d, date):
        raise InvalidDateError("solar date %r 不是 date 对象" % (d,))
    if d < SOLAR_MIN_DATE or d > SOLAR_MAX_DATE:
        raise OutOfRangeError(
            "公历日期 %s 超出支持范围 %s..%s"
            % (d.isoformat(), SOLAR_MIN_DATE.isoformat(), SOLAR_MAX_DATE.isoformat())
        )


def solar_to_lunar(d: date) -> LunarDate:
    """Convert a Gregorian ``date`` to its :class:`LunarDate`."""
    _validate_solar(d)
    offset = (d - _data.LUNAR_BASE).days
    year = _data.LUNAR_MIN_YEAR
    while year <= _data.LUNAR_TABLE_MAX_YEAR:
        if offset < _data.year_days(year):
            break
        offset -= _data.year_days(year)
        year += 1
    else:  # pragma: no cover - guarded by the range validation above
        raise OutOfRangeError("公历日期 %s 超出农历数据表范围" % d.isoformat())

    for month, is_leap, days in _data.year_months(year):
        if offset < days:
            day = offset + 1
            return LunarDate(year, month, day, is_leap, lunar_text(year, month, day, is_leap))
        offset -= days

    raise OutOfRangeError("无法定位农历日期 %s" % d.isoformat())  # pragma: no cover


def _year_offset_before(year: int) -> int:
    return sum(_data.year_days(y) for y in range(_data.LUNAR_MIN_YEAR, year))


def lunar_to_solar(year: int, month: int, day: int, is_leap_month: bool = False) -> date:
    """Convert a Chinese lunar date to the matching Gregorian ``date``."""
    _validate_lunar(year, month, day, is_leap_month)
    offset = _year_offset_before(year)
    for m, is_leap, days in _data.year_months(year):
        if m == month and is_leap == is_leap_month:
            return _data.LUNAR_BASE + timedelta(days=offset + day - 1)
        offset += days
    raise InvalidDateError(  # pragma: no cover - validated above
        "农历 %d 年不存在%s%d月" % (year, "闰" if is_leap_month else "", month)
    )