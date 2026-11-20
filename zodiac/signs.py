"""Solar (sun) sign lookup using the fixed date boundaries from the spec."""

from __future__ import annotations

from datetime import date
from typing import Tuple

# (sign_zh, sign_en, start_month, start_day)
SIGN_TABLE: Tuple[Tuple[str, str, int, int], ...] = (
    ("白羊座", "Aries", 3, 21),
    ("金牛座", "Taurus", 4, 20),
    ("双子座", "Gemini", 5, 21),
    ("巨蟹座", "Cancer", 6, 22),
    ("狮子座", "Leo", 7, 23),
    ("处女座", "Virgo", 8, 23),
    ("天秤座", "Libra", 9, 23),
    ("天蝎座", "Scorpio", 10, 24),
    ("射手座", "Sagittarius", 11, 23),
    ("摩羯座", "Capricorn", 12, 22),
    ("水瓶座", "Aquarius", 1, 20),
    ("双鱼座", "Pisces", 2, 19),
)

_CAPRICORN = ("摩羯座", "Capricorn", 12, 22)

# Chronological order starting at the beginning of the year.
_CHRONOLOGICAL = sorted(SIGN_TABLE, key=lambda item: (item[2], item[3]))


def get_sign(day: date) -> Tuple[str, str]:
    """Return ``(sign_zh, sign_en)`` for a calendar ``date``."""
    key = (day.month, day.day)
    current = _CAPRICORN
    for sign in _CHRONOLOGICAL:
        if key >= (sign[2], sign[3]):
            current = sign
        else:
            break
    return current[0], current[1]