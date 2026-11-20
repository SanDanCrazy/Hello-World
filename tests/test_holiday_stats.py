"""holiday_stats 的单元测试（标准库 unittest）。"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import holiday_stats as hs  # noqa: E402


def make_raw(**overrides):
    year_data = {
        "source": "test",
        "holidays": [
            {"name": "元旦", "start": "2025-01-01", "end": "2025-01-01", "statutory_days": 1}
        ],
        "makeup_workdays": ["2025-01-26"],
    }
    year_data.update(overrides.pop("year_data", {}))
    raw = {"country": "CN", "years": {"2025": year_data}}
    raw.update(overrides)
    return raw


class TestDays(unittest.TestCase):
    def test_single_day(self):
        holiday = hs.Holiday("元旦", date(2025, 1, 1), date(2025, 1, 1), 1)
        self.assertEqual(holiday.days, 1)

    def test_cross_month(self):
        holiday = hs.Holiday("春节", date(2025, 1, 28), date(2025, 2, 4), 4)
        self.assertEqual(holiday.days, 8)

    def test_cross_year(self):
        holiday = hs.Holiday("跨年", date(2024, 12, 30), date(2025, 1, 2), 1)
        self.assertEqual(holiday.days, 4)


class TestSummarize(unittest.TestCase):
    def setUp(self):
        self.data = hs.load_data(hs.default_data_path())

    def test_2025_summary(self):
        summary = hs.summarize(self.data[2025])
        self.assertEqual(summary.total_days, 28)
        self.assertEqual(summary.statutory_days, 13)
        self.assertEqual(summary.makeup_workdays, 5)
        self.assertEqual(summary.net_rest_days, 23)

    def test_2024_summary(self):
        summary = hs.summarize(self.data[2024])
        self.assertEqual(summary.total_days, 30)
        self.assertEqual(summary.statutory_days, 11)
        self.assertEqual(summary.makeup_workdays, 8)
        self.assertEqual(summary.net_rest_days, 22)

    def test_2025_holiday_days(self):
        days = [holiday.days for holiday in self.data[2025].holidays]
        self.assertEqual(days, [1, 8, 3, 5, 3, 8])

    def test_empty_makeup(self):
        plan = hs.YearPlan(
            2025,
            "test",
            (hs.Holiday("元旦", date(2025, 1, 1), date(2025, 1, 1), 1),),
            (),
        )
        summary = hs.summarize(plan)
        self.assertEqual(summary.makeup_workdays, 0)
        self.assertEqual(summary.net_rest_days, summary.total_days)


class TestValidate(unittest.TestCase):
    def test_valid(self):
        plans = hs.validate_data(make_raw())
        self.assertEqual(sorted(plans), [2025])
        self.assertEqual(plans[2025].holidays[0].name, "元旦")

    def test_missing_years(self):
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data({"country": "CN"})
        self.assertIn("years", str(ctx.exception))

    def test_bad_date_format(self):
        raw = make_raw(year_data={"holidays": [
            {"name": "元旦", "start": "2025/01/01", "end": "2025-01-01", "statutory_days": 1}
        ]})
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data(raw)
        self.assertIn("格式非法", str(ctx.exception))

    def test_end_before_start(self):
        raw = make_raw(year_data={"holidays": [
            {"name": "元旦", "start": "2025-01-02", "end": "2025-01-01", "statutory_days": 1}
        ]})
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data(raw)
        self.assertIn("早于 start", str(ctx.exception))

    def test_statutory_out_of_range(self):
        raw = make_raw(year_data={"holidays": [
            {"name": "元旦", "start": "2025-01-01", "end": "2025-01-01", "statutory_days": 2}
        ]})
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data(raw)
        self.assertIn("statutory_days", str(ctx.exception))

    def test_makeup_inside_holiday(self):
        raw = make_raw(year_data={"makeup_workdays": ["2025-01-01"]})
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data(raw)
        self.assertIn("落在", str(ctx.exception))

    def test_start_year_mismatch(self):
        raw = make_raw(year_data={"holidays": [
            {"name": "元旦", "start": "2024-12-31", "end": "2025-01-01", "statutory_days": 1}
        ]})
        with self.assertRaises(hs.DataError) as ctx:
            hs.validate_data(raw)
        self.assertIn("起始日期不在", str(ctx.exception))

    def test_empty_holidays(self):
        raw = make_raw(year_data={"holidays": []})
        with self.assertRaises(hs.DataError):
            hs.validate_data(raw)


class TestReport(unittest.TestCase):
    def setUp(self):
        self.data = hs.load_data(hs.default_data_path())

    def test_order_and_dedupe(self):
        report = hs.build_report([2025, 2024, 2025], self.data)
        self.assertEqual([entry["year"] for entry in report], [2024, 2025])

    def test_all_covers_every_year(self):
        report = hs.build_report(sorted(self.data), self.data)
        self.assertEqual([entry["year"] for entry in report], sorted(self.data))
        self.assertEqual(len(report), 2)

    def test_json_structure(self):
        report = hs.build_report([2025], self.data)
        payload = json.loads(hs.render_json(report))
        self.assertEqual(payload["country"], "CN")
        self.assertEqual(len(payload["years"]), 1)
        entry = payload["years"][0]
        self.assertEqual(entry["year"], 2025)
        self.assertEqual(len(entry["holidays"]), 6)
        self.assertEqual(entry["holidays"][0]["days"], 1)
        self.assertEqual(entry["summary"]["total_days"], 28)
        self.assertEqual(entry["summary"]["statutory_days"], 13)
        self.assertEqual(entry["summary"]["makeup_workdays"], 5)
        self.assertEqual(entry["summary"]["net_rest_days"], 23)

    def test_parse_year_args(self):
        self.assertEqual(hs.parse_year_args(["2025,2024", "2024"]), [2024, 2025])
        with self.assertRaises(hs.UsageError):
            hs.parse_year_args(["25"])

    def test_table_contains_summary(self):
        table = hs.render_table(hs.build_report([2025], self.data))
        self.assertIn("2025", table)
        self.assertIn("国庆节/中秋节", table)
        self.assertIn("净休息 23 天", table)


class TestCli(unittest.TestCase):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hs.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_year_ok(self):
        code, out, err = self.run_cli(["--year", "2025"])
        self.assertEqual(code, 0)
        self.assertIn("小计：放假 28 天", out)
        self.assertEqual(err, "")

    def test_multi_year_json(self):
        code, out, _ = self.run_cli(["--year", "2024", "--year", "2025", "--format", "json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual([entry["year"] for entry in payload["years"]], [2024, 2025])

    def test_unsupported_year(self):
        code, out, err = self.run_cli(["--year", "2019"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("不支持年份", err)
        self.assertIn("2024, 2025", err)

    def test_mutually_exclusive(self):
        code, _, err = self.run_cli(["--all", "--year", "2025"])
        self.assertEqual(code, 1)
        self.assertIn("参数错误", err)

    def test_no_args_prints_help(self):
        code, out, _ = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertIn("usage", out)

    def test_bad_data_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            code, out, err = self.run_cli(["--year", "2025", "--data", str(bad)])
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("数据错误", err)

    def test_all(self):
        code, out, _ = self.run_cli(["--all"])
        self.assertEqual(code, 0)
        self.assertIn("== 2024 年 ==", out)
        self.assertIn("== 2025 年 ==", out)

    def test_table_default(self):
        code, out, _ = self.run_cli(["--year", "2024"])
        self.assertEqual(code, 0)
        self.assertIn("小计：放假 30 天", out)


class TestEncoding(unittest.TestCase):
    def test_json_not_escaped(self):
        data = hs.load_data(hs.default_data_path())
        text = hs.render_json(hs.build_report([2025], data))
        self.assertIn("元旦", text)
        self.assertNotIn("\\u", text)
        self.assertIsInstance(text.encode("utf-8").decode("utf-8"), str)


if __name__ == "__main__":
    unittest.main()