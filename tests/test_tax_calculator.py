"""tax_calculator 的单元测试（标准库 unittest，零第三方依赖）。

运行::

    cd Hello-World && python3 -m unittest discover -s tests -v
"""

import json
import re
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tax_calculator  # noqa: E402
from tax_calculator import TAX_BRACKETS, calc_monthly_tax  # noqa: E402

SCRIPT = REPO_ROOT / "tax_calculator.py"
MONEY_PATTERN = re.compile(r"^-?\d+\.\d{2}$")


def run_cli(*args):
    """以子进程方式运行脚本，返回 CompletedProcess。"""
    return subprocess.run(
        [sys.executable, "tax_calculator.py", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


class TestTaxBrackets(unittest.TestCase):
    """AC-15：档位归属与边界值。"""

    CASES = [
        ("36000", "0.03", "0"),
        ("36000.01", "0.10", "2520"),
        ("144000", "0.10", "2520"),
        ("144000.01", "0.20", "16920"),
        ("300000", "0.20", "16920"),
        ("300000.01", "0.25", "31920"),
        ("420000", "0.25", "31920"),
        ("420000.01", "0.30", "52920"),
        ("660000", "0.30", "52920"),
        ("660000.01", "0.35", "85920"),
        ("960000", "0.35", "85920"),
        ("960000.01", "0.45", "181920"),
    ]

    def test_boundaries(self):
        for taxable, rate, quick in self.CASES:
            with self.subTest(taxable=taxable):
                got_rate, got_quick = tax_calculator._select_bracket(Decimal(taxable))
                self.assertEqual(got_rate, Decimal(rate))
                self.assertEqual(got_quick, Decimal(quick))

    def test_bracket_table_shape(self):
        self.assertEqual(len(TAX_BRACKETS), 7)
        self.assertIsNone(TAX_BRACKETS[-1][0])


class TestCalcCases(unittest.TestCase):
    """AC-1 ~ AC-10：固定用例精确相等。"""

    def assert_result(self, result, *, taxable, rate, quick, cum_tax, tax, net=None):
        self.assertEqual(result.cumulative_taxable_income, Decimal(taxable))
        self.assertEqual(result.tax_rate, Decimal(rate))
        self.assertEqual(result.quick_deduction, Decimal(quick))
        self.assertEqual(result.cumulative_tax, Decimal(cum_tax))
        self.assertEqual(result.tax_current, Decimal(tax))
        if net is not None:
            self.assertEqual(result.net_income, Decimal(net))

    def test_ac1(self):
        result = calc_monthly_tax(income=10000, month=1)
        self.assert_result(result, taxable="5000.00", rate="0.03", quick="0",
                           cum_tax="150.00", tax="150.00", net="9850.00")

    def test_ac2(self):
        result = calc_monthly_tax(
            income=10000, month=12,
            prior_cumulative_income=110000, prior_cumulative_tax=2980,
        )
        self.assert_result(result, taxable="60000.00", rate="0.10", quick="2520",
                           cum_tax="3480.00", tax="500.00")

    def test_ac3(self):
        result = calc_monthly_tax(
            income=30000, month=1, social_insurance=4500, special_additional=2000,
        )
        self.assert_result(result, taxable="18500.00", rate="0.03", quick="0",
                           cum_tax="555.00", tax="555.00", net="24945.00")

    def test_ac4(self):
        result = calc_monthly_tax(
            income=30000, month=12, social_insurance=4500, special_additional=2000,
            prior_cumulative_tax=23780, prior_cumulative_income=330000,
        )
        self.assert_result(result, taxable="222000.00", rate="0.20", quick="16920",
                           cum_tax="27480.00", tax="3700.00")

    def test_ac5(self):
        result = calc_monthly_tax(income=41000, month=1)
        self.assert_result(result, taxable="36000.00", rate="0.03", quick="0",
                           cum_tax="1080.00", tax="1080.00")

    def test_ac6(self):
        result = calc_monthly_tax(income=45000, month=1)
        self.assert_result(result, taxable="40000.00", rate="0.10", quick="2520",
                           cum_tax="1480.00", tax="1480.00")

    def test_ac7(self):
        result = calc_monthly_tax(income=1000000, month=1)
        self.assert_result(result, taxable="995000.00", rate="0.45", quick="181920",
                           cum_tax="265830.00", tax="265830.00")

    def test_ac8(self):
        result = calc_monthly_tax(
            income=10000, month=2,
            prior_cumulative_income=10000, prior_cumulative_tax=400,
        )
        self.assertEqual(result.cumulative_tax, Decimal("300.00"))
        self.assertEqual(result.tax_current, Decimal("0.00"))
        self.assertGreaterEqual(result.tax_current, Decimal("0"))

    def test_ac9(self):
        result = calc_monthly_tax(income=1000, month=1)
        self.assert_result(result, taxable="0.00", rate="0.03", quick="0",
                           cum_tax="0.00", tax="0.00")

    def test_ac10(self):
        result = calc_monthly_tax(income="5000.01", month=1)
        self.assert_result(result, taxable="0.01", rate="0.03", quick="0",
                           cum_tax="0.00", tax="0.00")


class TestDefaults(unittest.TestCase):
    """FR-3 / FR-4：默认值语义。"""

    def test_defaults_equal_explicit(self):
        implicit = calc_monthly_tax(income=20000, month=6)
        explicit = calc_monthly_tax(
            income=20000, month=6,
            prior_cumulative_income=100000, prior_cumulative_tax=0, prior_months=5,
        )
        self.assertEqual(implicit, explicit)

    def test_prior_months_overrides_month(self):
        overridden = calc_monthly_tax(income=20000, month=6, prior_months=2)
        self.assertEqual(overridden.cumulative_months, 3)
        self.assertEqual(overridden.cumulative_income, Decimal("60000.00"))
        self.assertEqual(overridden.month, 6)

    def test_string_and_decimal_inputs_agree(self):
        from_str = calc_monthly_tax(income="30000", month=1,
                                    social_insurance="4500", special_additional="2000")
        from_dec = calc_monthly_tax(income=Decimal("30000"), month=1,
                                    social_insurance=Decimal("4500"),
                                    special_additional=Decimal("2000"))
        self.assertEqual(from_str, from_dec)

    def test_deterministic(self):
        first = calc_monthly_tax(income=30000, month=12)
        second = calc_monthly_tax(income=30000, month=12)
        self.assertEqual(first, second)


class TestValidation(unittest.TestCase):
    """纯函数入参校验。"""

    def test_negative_income_rejected(self):
        with self.assertRaises(tax_calculator.InputError):
            calc_monthly_tax(income=-1, month=1)

    def test_bad_month_rejected(self):
        for month in (0, 13, 1.5, "1"):
            with self.subTest(month=month):
                with self.assertRaises(tax_calculator.InputError):
                    calc_monthly_tax(income=1000, month=month)

    def test_nan_and_inf_rejected(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                with self.assertRaises(tax_calculator.InputError):
                    calc_monthly_tax(income=value, month=1)


class TestJsonShape(unittest.TestCase):
    """AC-12：JSON 结构、键集合与金额格式。"""

    def test_json_keys_and_types(self):
        proc = run_cli("--income", "30000", "--month", "1",
                       "--social-insurance", "4500", "--special-additional", "2000",
                       "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        obj = json.loads(proc.stdout)
        self.assertEqual(set(obj), {
            "month", "income", "deductions", "cumulative_taxable_income",
            "tax_rate", "quick_deduction", "cumulative_tax", "tax_current",
            "net_income", "currency",
        })
        self.assertEqual(set(obj["deductions"]),
                         {"social_insurance", "special_additional", "other", "basic"})
        self.assertIsInstance(obj["month"], int)
        self.assertEqual(obj["currency"], "CNY")
        self.assertEqual(obj["income"], "30000.00")
        self.assertEqual(obj["deductions"]["basic"], "5000.00")
        self.assertEqual(obj["cumulative_taxable_income"], "18500.00")
        self.assertEqual(obj["tax_rate"], "0.03")
        self.assertEqual(obj["tax_current"], "555.00")
        self.assertEqual(obj["net_income"], "24945.00")
        for key in ("income", "cumulative_taxable_income", "quick_deduction",
                    "cumulative_tax", "tax_current", "net_income"):
            self.assertRegex(obj[key], MONEY_PATTERN, key)
        for value in obj["deductions"].values():
            self.assertRegex(value, MONEY_PATTERN)


class TestCliBehavior(unittest.TestCase):
    """AC-11 / AC-13 / AC-14。"""

    def test_invalid_inputs_exit_2_with_chinese(self):
        cases = [
            ("--income", "-100", "--month", "1"),
            ("--income", "abc", "--month", "1"),
            ("--income", "10000", "--month", "13"),
            ("--income", "10000", "--month", "0"),
            ("--month", "1"),
        ]
        for args in cases:
            with self.subTest(args=args):
                proc = run_cli(*args)
                self.assertEqual(proc.returncode, 2, (args, proc.stdout, proc.stderr))
                self.assertTrue(
                    any("\u4e00" <= ch <= "\u9fff" for ch in proc.stderr),
                    proc.stderr,
                )

    def test_help_lists_all_arguments(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        for name in ("--income", "--month", "--social-insurance", "--special-additional",
                     "--other-deduction", "--prior-cumulative-tax",
                     "--prior-cumulative-income", "--prior-months",
                     "--basic-deduction", "--json"):
            self.assertIn(name, proc.stdout)

    def test_human_output_contains_key_labels(self):
        proc = run_cli("--income", "30000", "--month", "1",
                       "--social-insurance", "4500", "--special-additional", "2000")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for label in ("累计应纳税所得额", "预扣率", "速算扣除数",
                      "累计应预扣税额", "本期应预扣税额", "税后收入"):
            self.assertIn(label, proc.stdout)
        self.assertIn("555.00", proc.stdout)
        self.assertIn("24945.00", proc.stdout)

    def test_deterministic_cli_output(self):
        args = ("--income", "30000", "--month", "12", "--json")
        first = run_cli(*args)
        second = run_cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_basic_deduction_override(self):
        proc = run_cli("--income", "10000", "--month", "1",
                       "--basic-deduction", "6000", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        obj = json.loads(proc.stdout)
        self.assertEqual(obj["deductions"]["basic"], "6000.00")
        self.assertEqual(obj["cumulative_taxable_income"], "4000.00")
        self.assertEqual(obj["tax_current"], "120.00")


class TestHumanDetail(unittest.TestCase):
    """FR-6：人类可读明细包含扣除合计（四项之和）。"""

    def test_human_output_contains_deduction_total(self):
        proc = run_cli("--income", "30000", "--month", "1",
                       "--social-insurance", "4500", "--special-additional", "2000")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("扣除合计", proc.stdout)
        total_line = next(
            line for line in proc.stdout.splitlines() if "扣除合计" in line)
        self.assertIn("11500.00", total_line)

    def test_human_output_deduction_total_defaults(self):
        proc = run_cli("--income", "10000", "--month", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        total_line = next(
            line for line in proc.stdout.splitlines() if "扣除合计" in line)
        self.assertIn("5000.00", total_line)


class TestMoreCliErrors(unittest.TestCase):
    """FR-5 补充：缺取值、超大金额、前缀缩写。"""

    def test_missing_option_value_is_chinese_exit_2(self):
        proc = run_cli("--income")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("缺少取值", proc.stderr)
        self.assertNotIn("expected one argument", proc.stderr)

    def test_huge_amount_is_rejected_with_chinese(self):
        for args in (("--income", "1e30", "--month", "1"),
                     ("--income", "1e25", "--month", "12")):
            with self.subTest(args=args):
                proc = run_cli(*args)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn("超出可计算范围", proc.stderr)

    def test_max_amount_is_accepted(self):
        proc = run_cli("--income", "1e15", "--month", "12", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["income"], "1000000000000000.00")

    def test_abbreviated_option_rejected(self):
        proc = run_cli("--inc", "10000", "--month", "1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("参数错误", proc.stderr)
        self.assertNotIn('"income": "10000.00"', proc.stdout)


class TestNegativeNetIncome(unittest.TestCase):
    """设计 §3.3：扣除大于收入时税后收入如实为负。"""

    def test_negative_net_income_json(self):
        proc = run_cli("--income", "1000", "--social-insurance", "2000",
                       "--month", "1", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        obj = json.loads(proc.stdout)
        self.assertEqual(obj["tax_current"], "0.00")
        self.assertEqual(obj["net_income"], "-1000.00")
        self.assertRegex(obj["net_income"], MONEY_PATTERN)


if __name__ == "__main__":
    unittest.main()
