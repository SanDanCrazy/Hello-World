#!/usr/bin/env python3
"""年度节假日时长统计脚本（中国大陆法定节假日）。

纯标准库实现，数据与逻辑分离。数据文件默认位于脚本同目录的
``data/cn_holidays.json``，也可通过 ``--data`` 指定。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class UsageError(Exception):
    """参数使用错误，映射到退出码 1。"""


class DataError(Exception):
    """数据文件缺失或校验失败，映射到退出码 3。"""


@dataclass(frozen=True)
class Holiday:
    name: str
    start: date
    end: date
    statutory_days: int

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class YearPlan:
    year: int
    source: str
    holidays: Tuple[Holiday, ...]
    makeup_workdays: Tuple[date, ...]


@dataclass(frozen=True)
class YearSummary:
    year: int
    total_days: int
    statutory_days: int
    makeup_workdays: int
    net_rest_days: int


def default_data_path() -> Path:
    """返回默认数据文件路径，与当前工作目录无关。"""
    return Path(__file__).resolve().parent / "data" / "cn_holidays.json"


def load_raw(path: Path) -> dict:
    """读取 UTF-8 JSON 文件，失败时抛出 DataError。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise DataError("数据文件不存在: {}".format(path))
    except OSError as exc:
        raise DataError("无法读取数据文件 {}: {}".format(path, exc))
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError("数据文件不是合法 JSON {}: {}".format(path, exc))
    if not isinstance(raw, dict):
        raise DataError("数据文件顶层必须为对象: {}".format(path))
    return raw


def parse_date(value: object, field: str, year: int) -> date:
    """严格解析 YYYY-MM-DD 日期，失败时抛出 DataError。"""
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise DataError("{} {} 日期格式非法: {!r}".format(year, field, value))
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise DataError("{} {} 日期非法: {!r}".format(year, field, value))


def _require_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_data(raw: dict) -> Dict[int, YearPlan]:
    """按约定校验原始数据并归一化为 {year: YearPlan}。"""
    years = raw.get("years")
    if not isinstance(years, dict):
        raise DataError("数据文件缺少 years 对象")
    if not years:
        raise DataError("数据文件 years 对象为空")

    plans: Dict[int, YearPlan] = {}
    for key, year_raw in years.items():
        if not isinstance(key, str) or not re.match(r"^\d{4}$", key):
            raise DataError("年份键非法: {!r}".format(key))
        year = int(key)
        if year in plans:
            raise DataError("年份重复: {}".format(year))
        if not isinstance(year_raw, dict):
            raise DataError("{} 的年度配置必须为对象".format(year))

        source = year_raw.get("source", "")
        if not isinstance(source, str):
            raise DataError("{} 的 source 必须为字符串".format(year))

        holidays_raw = year_raw.get("holidays")
        if not isinstance(holidays_raw, list) or not holidays_raw:
            raise DataError("{} 的 holidays 必须为非空数组".format(year))

        holidays: List[Holiday] = []
        for index, item in enumerate(holidays_raw, start=1):
            if not isinstance(item, dict):
                raise DataError("{} 第 {} 个节日必须为对象".format(year, index))
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                raise DataError("{} 第 {} 个节日缺少 name".format(year, index))
            start = parse_date(item.get("start"), "{} start".format(name), year)
            end = parse_date(item.get("end"), "{} end".format(name), year)
            if end < start:
                raise DataError("{} {} end 早于 start".format(year, name))
            statutory = item.get("statutory_days")
            days = (end - start).days + 1
            if not _require_int(statutory) or not (0 <= statutory <= days):
                raise DataError(
                    "{} {} statutory_days 超出范围: {!r}".format(year, name, statutory)
                )
            if start.year != year:
                raise DataError(
                    "{} 的节日 {} 起始日期不在 {} 年".format(year, name, year)
                )
            holidays.append(Holiday(name=name, start=start, end=end, statutory_days=statutory))

        makeup_raw = year_raw.get("makeup_workdays", [])
        if not isinstance(makeup_raw, list):
            raise DataError("{} 的 makeup_workdays 必须为数组".format(year))
        makeup: List[date] = []
        for value in makeup_raw:
            makeup.append(parse_date(value, "makeup_workdays", year))

        for workday in makeup:
            for holiday in holidays:
                if holiday.start <= workday <= holiday.end:
                    raise DataError(
                        "调休日 {} 落在 {} 放假区间内".format(workday.isoformat(), holiday.name)
                    )

        plans[year] = YearPlan(
            year=year,
            source=source,
            holidays=tuple(holidays),
            makeup_workdays=tuple(makeup),
        )

    return plans


def load_data(path: Path) -> Dict[int, YearPlan]:
    """加载并校验数据文件。"""
    return validate_data(load_raw(path))


def summarize(plan: YearPlan) -> YearSummary:
    """汇总年度放假天数、法定天数、调休上班天数与净休息天数。"""
    total_days = sum(holiday.days for holiday in plan.holidays)
    statutory_days = sum(holiday.statutory_days for holiday in plan.holidays)
    makeup_workdays = len(plan.makeup_workdays)
    return YearSummary(
        year=plan.year,
        total_days=total_days,
        statutory_days=statutory_days,
        makeup_workdays=makeup_workdays,
        net_rest_days=total_days - makeup_workdays,
    )


def build_report(years: List[int], data: Dict[int, YearPlan]) -> List[dict]:
    """按年份升序组装输出结构（明细 + 汇总）。"""
    report: List[dict] = []
    for year in sorted(set(years)):
        plan = data[year]
        summary = summarize(plan)
        report.append(
            {
                "year": year,
                "source": plan.source,
                "holidays": [
                    {
                        "name": holiday.name,
                        "start": holiday.start.isoformat(),
                        "end": holiday.end.isoformat(),
                        "days": holiday.days,
                        "statutory_days": holiday.statutory_days,
                    }
                    for holiday in plan.holidays
                ],
                "summary": {
                    "total_days": summary.total_days,
                    "statutory_days": summary.statutory_days,
                    "makeup_workdays": summary.makeup_workdays,
                    "net_rest_days": summary.net_rest_days,
                    "makeup_workday_dates": [
                        workday.isoformat() for workday in plan.makeup_workdays
                    ],
                },
            }
        )
    return report


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in "WF" else 1
    return width


def _pad(text: str, width: int, align: str = "left") -> str:
    filler = max(0, width - _display_width(text))
    if align == "right":
        return " " * filler + text
    return text + " " * filler


def render_table(report: List[dict]) -> str:
    """渲染按年分块的对齐纯文本表格。"""
    headers = ("节日", "开始日期", "结束日期", "放假天数", "法定天数")
    aligns = ("left", "left", "left", "right", "right")
    blocks: List[str] = []

    for entry in report:
        rows: List[Tuple[str, ...]] = [
            (
                holiday["name"],
                holiday["start"],
                holiday["end"],
                str(holiday["days"]),
                str(holiday["statutory_days"]),
            )
            for holiday in entry["holidays"]
        ]
        widths = [_display_width(header) for header in headers]
        for row in rows:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], _display_width(cell))

        def format_row(cells: Tuple[str, ...]) -> str:
            return "  ".join(
                _pad(cell, widths[index], aligns[index]) for index, cell in enumerate(cells)
            ).rstrip()

        lines = ["== {} 年 ==".format(entry["year"]), format_row(headers)]
        for row in rows:
            lines.append(format_row(row))
        summary = entry["summary"]
        lines.append(
            "小计：放假 {} 天 | 法定 {} 天 | 调休上班 {} 天 | 净休息 {} 天".format(
                summary["total_days"],
                summary["statutory_days"],
                summary["makeup_workdays"],
                summary["net_rest_days"],
            )
        )
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def render_json(report: List[dict]) -> str:
    """渲染稳定结构的 JSON（UTF-8，不转义中文）。"""
    payload = {"country": "CN", "years": report}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_year_args(values: List[str]) -> List[int]:
    """解析 --year 参数（可重复、可逗号分隔），去重后升序返回。"""
    years: List[int] = []
    for value in values:
        for part in value.split(","):
            token = part.strip()
            if not re.match(r"^\d{4}$", token):
                raise UsageError("年份格式非法: {!r}，应为四位数字年份".format(part))
            years.append(int(token))
    if not years:
        raise UsageError("未提供有效年份")
    return sorted(set(years))


class _Parser(argparse.ArgumentParser):
    """将 argparse 的参数错误转换为 UsageError，避免退出码 2。"""

    def error(self, message: str) -> None:  # pragma: no cover - 直接测试 main
        raise UsageError(message)


def _build_parser() -> _Parser:
    parser = _Parser(
        prog="holiday_stats.py",
        description="统计中国大陆法定节假日的年度放假时长。",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--year",
        action="append",
        metavar="YYYY",
        help="查询年份，可重复传入或用逗号分隔，如：--year 2025 --year 2024",
    )
    group.add_argument("--all", action="store_true", help="输出数据文件中的全部年度")
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="输出格式，默认 table",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="自定义数据文件路径，默认 data/cn_holidays.json",
    )
    return parser


def _configure_stdout() -> None:
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口，返回进程退出码。"""
    parser = _build_parser()
    args_list = list(sys.argv[1:] if argv is None else argv)

    try:
        args = parser.parse_args(args_list)
    except UsageError as exc:
        print("参数错误: {}".format(exc), file=sys.stderr)
        return 1

    if args.year is None and not args.all:
        print(parser.format_help(), end="")
        return 1

    try:
        if args.year is not None:
            years = parse_year_args(args.year)
        else:
            years = []
    except UsageError as exc:
        print("参数错误: {}".format(exc), file=sys.stderr)
        return 1

    path = args.data if args.data is not None else default_data_path()

    try:
        data = load_data(path)
    except DataError as exc:
        print("数据错误: {}".format(exc), file=sys.stderr)
        return 3

    if not years:
        years = sorted(data)

    missing = [year for year in years if year not in data]
    if missing:
        supported = ", ".join(str(year) for year in sorted(data))
        print(
            "不支持年份 {}，已支持年份：{}".format(", ".join(str(y) for y in missing), supported),
            file=sys.stderr,
        )
        return 2

    report = build_report(years, data)
    _configure_stdout()
    if args.format == "json":
        print(render_json(report))
    else:
        print(render_table(report))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # pragma: no cover
        raise SystemExit(1)