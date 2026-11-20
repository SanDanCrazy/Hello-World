"""Offline test suite for the zodiac package (covers AC-01 .. AC-24)."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import time
import unittest
from datetime import date, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from zodiac import (  # noqa: E402
    InvalidDateError,
    OutOfRangeError,
    ZodiacError,
    ZodiacResult,
    get_zodiac,
    lunar_to_solar,
    solar_to_lunar,
)
from zodiac import calendar_data  # noqa: E402
from zodiac.signs import SIGN_TABLE, get_sign  # noqa: E402

CHRONOLOGICAL = sorted(SIGN_TABLE, key=lambda item: (item[2], item[3]))


def _previous_sign(sign):
    index = CHRONOLOGICAL.index(sign)
    return CHRONOLOGICAL[index - 1]


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "zodiac", *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class DataTableTests(unittest.TestCase):
    """AC-22 support and design 6.2 data integrity invariants."""

    def test_table_length(self):
        self.assertEqual(len(calendar_data.LUNAR_INFO), 201)

    def test_month_lengths_and_leap_values(self):
        for year in range(1900, 2101):
            leap = calendar_data.leap_month(year)
            self.assertIn(leap, range(0, 13), year)
            for month, is_leap, days in calendar_data.year_months(year):
                self.assertIn(days, (29, 30), (year, month, is_leap))
            total = calendar_data.year_days(year)
            if leap:
                self.assertIn(total, (383, 384, 385), year)
            else:
                self.assertIn(total, (353, 354, 355), year)

    def test_spring_festival_anchors(self):
        anchors = {
            1900: date(1900, 1, 31),
            1949: date(1949, 1, 29),
            1984: date(1984, 2, 2),
            2000: date(2000, 2, 5),
            2020: date(2020, 1, 25),
            2021: date(2021, 2, 12),
            2022: date(2022, 2, 1),
            2023: date(2023, 1, 22),
            2024: date(2024, 2, 10),
            2025: date(2025, 1, 29),
            2033: date(2033, 1, 31),
            2034: date(2034, 2, 19),
        }
        for year, expected in anchors.items():
            self.assertEqual(lunar_to_solar(year, 1, 1), expected, year)

    def test_leap_month_anchors(self):
        # (year, month, start, end)
        anchors = [
            (2020, 4, date(2020, 5, 23), date(2020, 6, 20)),
            (2023, 2, date(2023, 3, 22), date(2023, 4, 19)),
            (2033, 11, date(2033, 12, 22), date(2034, 1, 19)),
        ]
        for year, month, start, end in anchors:
            self.assertTrue(calendar_data.leap_month(year) == month)
            self.assertEqual(lunar_to_solar(year, month, 1, True), start)
            last = calendar_data.leap_days(year)
            self.assertEqual(lunar_to_solar(year, month, last, True), end)


class SignTests(unittest.TestCase):
    """AC-01 .. AC-06, AC-05."""

    def test_sign_boundary_known(self):
        cases = {
            (2024, 3, 21): ("白羊座", "Aries"),
            (2024, 3, 20): ("双鱼座", "Pisces"),
            (2024, 12, 22): ("摩羯座", "Capricorn"),
            (2024, 12, 21): ("射手座", "Sagittarius"),
        }
        for (year, month, day), expected in cases.items():
            result = get_zodiac(year, month, day)
            self.assertEqual((result.sign_zh, result.sign_en), expected)

    def test_all_sign_boundaries(self):
        for sign in CHRONOLOGICAL:
            start = date(2024, sign[2], sign[3])
            previous = start - timedelta(days=1)
            current = get_zodiac(start.year, start.month, start.day)
            self.assertEqual((current.sign_zh, current.sign_en), (sign[0], sign[1]))
            before = get_zodiac(previous.year, previous.month, previous.day)
            prev_sign = _previous_sign(sign)
            self.assertEqual(
                (before.sign_zh, before.sign_en), (prev_sign[0], prev_sign[1])
            )

    def test_leap_day_valid(self):
        result = get_zodiac(2024, 2, 29)
        self.assertEqual(result.sign_zh, "双鱼座")
        self.assertEqual(result.solar_date, date(2024, 2, 29))

    def test_whole_year_is_partitioned(self):
        for year in (2023, 2024):
            day = date(year, 1, 1)
            end = date(year, 12, 31)
            seen = set()
            while day <= end:
                sign = get_sign(day)
                self.assertIn((sign[0], sign[1]), [(s[0], s[1]) for s in SIGN_TABLE])
                seen.add(sign)
                day += timedelta(days=1)
            self.assertEqual(seen, {(s[0], s[1]) for s in SIGN_TABLE})


class CalendarValidationTests(unittest.TestCase):
    """AC-07, AC-08, AC-12, AC-14, AC-15 and API input checks."""

    def test_invalid_solar_dates(self):
        for args in [(2023, 2, 29), (2024, 13, 1), (2024, 0, 1), (2024, 1, 0), (2024, 4, 31)]:
            with self.assertRaises(InvalidDateError):
                get_zodiac(*args)

    def test_invalid_lunar_dates(self):
        cases = [
            (2024, 2, 1, True),   # 2024 has no leap second month
            (2023, 1, 1, True),   # 2023 leap month is 2, not 1
            (2024, 1, 31, False), # day 31 never valid
            (2024, 13, 1, False), # month 13 invalid
        ]
        for year, month, day, leap in cases:
            with self.assertRaises(InvalidDateError):
                get_zodiac(year, month, day, calendar="lunar", is_leap_month=leap)

    def test_month_thirty_must_exist(self):
        # 2024 second lunar month has 30 days, first only 29.
        self.assertEqual(calendar_data.month_days(2024, 2), 30)
        self.assertEqual(calendar_data.month_days(2024, 1), 29)
        get_zodiac(2024, 2, 30, calendar="lunar")
        with self.assertRaises(InvalidDateError):
            get_zodiac(2024, 1, 30, calendar="lunar")

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(InvalidDateError, ValueError))
        self.assertTrue(issubclass(OutOfRangeError, ValueError))
        self.assertTrue(issubclass(InvalidDateError, ZodiacError))

    def test_out_of_range_solar(self):
        for args in [(1900, 1, 1), (2101, 1, 1), (1899, 12, 31)]:
            with self.assertRaises(OutOfRangeError):
                get_zodiac(*args)
        with self.assertRaises(OutOfRangeError) as ctx:
            get_zodiac(1899, 12, 31)
        self.assertIn("范围", str(ctx.exception))

    def test_out_of_range_lunar(self):
        for args in [(1899, 12, 1), (2100, 1, 1)]:
            with self.assertRaises(OutOfRangeError):
                get_zodiac(*args, calendar="lunar")

    def test_invalid_calendar_value(self):
        with self.assertRaises(ValueError):
            get_zodiac(2024, 1, 1, calendar="foo")

    def test_leap_flag_rejected_for_solar(self):
        with self.assertRaises(InvalidDateError):
            get_zodiac(2024, 1, 1, calendar="solar", is_leap_month=True)


class LunarQueryTests(unittest.TestCase):
    """AC-09 .. AC-13."""

    def test_lunar_2024_new_year(self):
        result = get_zodiac(2024, 1, 1, calendar="lunar")
        self.assertEqual(result.solar_date, date(2024, 2, 10))
        self.assertEqual(result.sign_zh, "水瓶座")
        self.assertEqual(result.sign_en, "Aquarius")
        self.assertEqual((result.lunar_year, result.lunar_month, result.lunar_day), (2024, 1, 1))
        self.assertFalse(result.is_leap_month)
        self.assertEqual(result.lunar_text, "农历二〇二四年正月初一")
        self.assertEqual(result.input_calendar, "lunar")

    def test_lunar_2025_new_year(self):
        result = get_zodiac(2025, 1, 1, calendar="lunar")
        self.assertEqual(result.solar_date, date(2025, 1, 29))
        self.assertEqual(result.sign_zh, "水瓶座")

    def test_lunar_2023_leap_second(self):
        result = get_zodiac(2023, 2, 1, calendar="lunar", is_leap_month=True)
        self.assertEqual(result.solar_date, date(2023, 3, 22))
        self.assertEqual(result.sign_zh, "白羊座")
        self.assertTrue(result.is_leap_month)
        self.assertEqual(result.lunar_text, "农历二〇二三年闰二月初一")

    def test_lunar_2023_new_year(self):
        result = get_zodiac(2023, 1, 1, calendar="lunar", is_leap_month=False)
        self.assertEqual(result.solar_date, date(2023, 1, 22))
        self.assertEqual(result.sign_zh, "水瓶座")

    def test_solar_result_reports_lunar(self):
        result = get_zodiac(2024, 2, 10)
        self.assertEqual(result.input_calendar, "solar")
        self.assertEqual((result.lunar_year, result.lunar_month, result.lunar_day), (2024, 1, 1))
        self.assertEqual(result.lunar_text, "农历二〇二四年正月初一")


class RoundTripTests(unittest.TestCase):
    """AC-21 and design 6.2 monotonicity."""

    def test_round_trip_sampling(self):
        day = date(1900, 1, 31)
        end = date(2100, 12, 31)
        checked = 0
        while day <= end:
            lunar = solar_to_lunar(day)
            back = lunar_to_solar(lunar.year, lunar.month, lunar.day, lunar.is_leap_month)
            self.assertEqual(back, day, day)
            checked += 1
            day += timedelta(days=37)
        self.assertGreater(checked, 1900)

    def test_lunar_to_solar_is_monotonic(self):
        previous = None
        for year in range(1900, 2101):
            for month, is_leap, days in calendar_data.year_months(year):
                for day in range(1, days + 1):
                    solar = lunar_to_solar(year, month, day, is_leap)
                    if previous is not None:
                        self.assertEqual((solar - previous).days, 1)
                    previous = solar


class ResultContractTests(unittest.TestCase):
    """AC-23."""

    def test_result_fields_and_frozen(self):
        expected = {
            "sign_zh",
            "sign_en",
            "solar_date",
            "lunar_year",
            "lunar_month",
            "lunar_day",
            "is_leap_month",
            "lunar_text",
            "input_calendar",
        }
        self.assertEqual({f.name for f in dataclasses.fields(ZodiacResult)}, expected)
        result = get_zodiac(1990, 8, 15)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.sign_zh = "白羊座"

    def test_result_to_dict(self):
        result = get_zodiac(2024, 1, 1, calendar="lunar")
        payload = result.to_dict()
        self.assertEqual(payload["solar_date"], "2024-02-10")
        self.assertFalse(payload["is_leap_month"])

    def test_import_has_no_side_effect(self):
        completed = subprocess.run(
            [sys.executable, "-c", "import zodiac"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr, "")


class PerformanceTests(unittest.TestCase):
    """NFR-4: a single lookup should be well under 50 ms."""

    def test_repeated_lookups_are_fast(self):
        start = time.perf_counter()
        for _ in range(1000):
            get_zodiac(1990, 8, 15)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5.0)


class CliTests(unittest.TestCase):
    """AC-16 .. AC-20."""

    def test_cli_lunar_human(self):
        completed = _run_cli("--calendar", "lunar", "--date", "2024-01-01")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("公历: 2024-02-10", completed.stdout)
        self.assertIn("星座: 水瓶座 (Aquarius)", completed.stdout)

    def test_cli_lunar_leap_json(self):
        completed = _run_cli(
            "--calendar", "lunar", "--date", "2023-02-01", "--leap", "--json"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count("\n"), 1)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["is_leap_month"])
        self.assertEqual(payload["sign_zh"], "白羊座")
        self.assertEqual(payload["solar_date"], "2023-03-22")

    def test_cli_solar_default(self):
        completed = _run_cli("--date", "1990-08-15")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("公历: 1990-08-15", completed.stdout)
        self.assertIn("星座: 狮子座 (Leo)", completed.stdout)

    def test_cli_invalid_solar_day(self):
        completed = _run_cli("--calendar", "solar", "--date", "2023-02-29")
        self.assertEqual(completed.returncode, 2)
        self.assertTrue(completed.stderr.strip())
        self.assertNotIn("星座", completed.stdout)

    def test_cli_out_of_range(self):
        completed = _run_cli("--calendar", "solar", "--date", "1899-12-31")
        self.assertEqual(completed.returncode, 3)
        self.assertIn("范围", completed.stderr)
        self.assertNotIn("星座", completed.stdout)

    def test_cli_argument_errors(self):
        cases = [
            (),
            ("--date", "2024/01/01"),
            ("--date", "not-a-date"),
            ("--calendar", "solar", "--date", "2024-01-01", "--leap"),
            ("--calendar", "foo", "--date", "2024-01-01"),
        ]
        for args in cases:
            completed = _run_cli(*args)
            self.assertEqual(completed.returncode, 2, args)
            self.assertNotIn("星座", completed.stdout)

    def test_cli_help(self):
        completed = _run_cli("--help")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("--calendar", completed.stdout)
        self.assertIn("--date", completed.stdout)


if __name__ == "__main__":
    unittest.main()