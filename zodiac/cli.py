"""Command line entry point: ``python -m zodiac``."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import List, Optional

from .api import get_zodiac
from .errors import InvalidDateError, OutOfRangeError

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INVALID = 2
EXIT_OUT_OF_RANGE = 3


def _parse_date(raw: str) -> tuple:
    match = _DATE_RE.match(raw)
    if not match:
        raise InvalidDateError("日期 %r 格式错误，应为 YYYY-MM-DD" % (raw,))
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _reconfigure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):  # pragma: no cover - platform specific
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m zodiac",
        description="根据公历或农历生日计算星座。",
        epilog=(
            "示例:\n"
            "  python -m zodiac --date 1990-08-15\n"
            "  python -m zodiac --calendar lunar --date 2024-01-01\n"
            "  python -m zodiac --calendar lunar --date 2023-02-01 --leap --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--calendar",
        choices=("solar", "lunar"),
        default="solar",
        help="输入历法，默认 solar（公历）",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="日期 YYYY-MM-DD；农历时为农历年月日",
    )
    parser.add_argument(
        "--leap",
        action="store_true",
        help="仅农历有效，表示该月为闰月",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="输出单行 JSON",
    )
    return parser


def _format_human(result) -> str:
    return "\n".join(
        (
            "公历: %s" % result.solar_date.isoformat(),
            "农历: %s" % result.lunar_text,
            "星座: %s (%s)" % (result.sign_zh, result.sign_en),
        )
    )


def _format_json(result) -> str:
    payload = {
        "input_calendar": result.input_calendar,
        "solar_date": result.solar_date.isoformat(),
        "lunar_year": result.lunar_year,
        "lunar_month": result.lunar_month,
        "lunar_day": result.lunar_day,
        "is_leap_month": result.is_leap_month,
        "lunar_text": result.lunar_text,
        "sign_zh": result.sign_zh,
        "sign_en": result.sign_en,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def main(argv: Optional[List[str]] = None) -> int:
    _reconfigure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.leap and args.calendar == "solar":
        parser.error("--leap 只能与 --calendar lunar 一起使用")

    try:
        year, month, day = _parse_date(args.date)
    except InvalidDateError as exc:
        parser.error(str(exc))

    try:
        result = get_zodiac(
            year,
            month,
            day,
            calendar=args.calendar,
            is_leap_month=args.leap,
        )
    except InvalidDateError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return EXIT_INVALID
    except OutOfRangeError as exc:
        print("错误: %s" % exc, file=sys.stderr)
        return EXIT_OUT_OF_RANGE
    except Exception as exc:  # noqa: BLE001 - never print a fake result
        print("内部错误: %s" % exc, file=sys.stderr)
        return EXIT_INTERNAL

    output = _format_json(result) if args.as_json else _format_human(result)
    print(output)
    return EXIT_OK


__all__ = ["main", "build_parser"]