"""个人所得税计算脚本（居民个人工资薪金所得，累计预扣预缴法）。

CLI: python3 tax_calculator.py --income 30000 --month 1 --social-insurance 4500
函数: from tax_calculator import calc_monthly_tax

金额全程 Decimal + ROUND_HALF_UP 保留 2 位小数；不做年度汇算清缴，负税额按 0 计且不结转。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional, Tuple

TAX_BRACKETS: Tuple[Tuple[Optional[Decimal], Decimal, Decimal], ...] = (
    (Decimal("36000"), Decimal("0.03"), Decimal("0")),
    (Decimal("144000"), Decimal("0.10"), Decimal("2520")),
    (Decimal("300000"), Decimal("0.20"), Decimal("16920")),
    (Decimal("420000"), Decimal("0.25"), Decimal("31920")),
    (Decimal("660000"), Decimal("0.30"), Decimal("52920")),
    (Decimal("960000"), Decimal("0.35"), Decimal("85920")),
    (None, Decimal("0.45"), Decimal("181920")),
)
DEFAULT_BASIC_DEDUCTION = Decimal("5000")
MAX_AMOUNT = Decimal("1000000000000000")
MONEY = Decimal("0.01")
CURRENCY = "CNY"


class InputError(ValueError):
    """入参非法（CLI 层翻译为中文提示并以退出码 2 结束）。"""


def _q(value: Decimal) -> Decimal:
    """金额量化到分，舍入固定 ROUND_HALF_UP。"""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _amount(name: str, value: Decimal | str | int) -> Decimal:
    """校验金额为 [0, MAX_AMOUNT] 内的有限数值并量化到分。"""
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise InputError(f"{name} 必须为非负数值，收到：{value}") from None
    if not value.is_finite() or value < 0:
        raise InputError(f"{name} 必须为非负数值，收到：{value}")
    if value > MAX_AMOUNT:
        raise InputError(f"{name} 超出可计算范围（上限 {MAX_AMOUNT} 元），收到：{value}")
    return _q(value)


def _select_bracket(taxable: Decimal) -> Tuple[Decimal, Decimal]:
    """按「不超过上限」查档（边界归低档），返回 (税率, 速算扣除数)。"""
    for upper, rate, quick in TAX_BRACKETS:
        if upper is None or taxable <= upper:
            return rate, quick
    _, rate, quick = TAX_BRACKETS[-1]
    return rate, quick


@dataclass(frozen=True)
class TaxResult:
    """单月计算的结构化结果（金额为 2 位小数的 Decimal）。"""

    month: int
    income: Decimal
    social_insurance: Decimal
    special_additional: Decimal
    other_deduction: Decimal
    basic_deduction: Decimal
    cumulative_months: int
    cumulative_income: Decimal
    cumulative_taxable_income: Decimal
    tax_rate: Decimal
    quick_deduction: Decimal
    cumulative_tax: Decimal
    tax_current: Decimal
    net_income: Decimal

    def as_json_dict(self) -> Dict[str, object]:
        """序列化为需求 6.3 规定的 JSON 结构（金额为 2 位小数字符串）。"""
        return {
            "month": self.month, "income": str(self.income),
            "deductions": {"social_insurance": str(self.social_insurance),
                           "special_additional": str(self.special_additional),
                           "other": str(self.other_deduction),
                           "basic": str(self.basic_deduction)},
            "cumulative_taxable_income": str(self.cumulative_taxable_income),
            "tax_rate": str(self.tax_rate), "quick_deduction": str(self.quick_deduction),
            "cumulative_tax": str(self.cumulative_tax),
            "tax_current": str(self.tax_current), "net_income": str(self.net_income),
            "currency": CURRENCY,
        }


def calc_monthly_tax(
    *, income: Decimal | str | int, month: int,
    social_insurance: Decimal | str | int = 0,
    special_additional: Decimal | str | int = 0,
    other_deduction: Decimal | str | int = 0,
    prior_cumulative_tax: Decimal | str | int = 0,
    prior_cumulative_income: Decimal | str | int | None = None,
    prior_months: Optional[int] = None,
    basic_deduction: Decimal | str | int = DEFAULT_BASIC_DEDUCTION,
) -> TaxResult:
    """计算居民个人工资薪金所得当月应预扣预缴税额与税后收入。

    纯函数：不读环境、不写文件、不打印，同一输入恒等输出。累计收入未显式
    传入时按 ``月收入 × (已计税月数 - 1)`` 推算；``prior_months`` 缺省为
    ``month - 1``；``prior_cumulative_tax`` 缺省 0。
    """
    income_d = _amount("income", income)
    social_d = _amount("social_insurance", social_insurance)
    special_d = _amount("special_additional", special_additional)
    other_d = _amount("other_deduction", other_deduction)
    basic_d = _amount("basic_deduction", basic_deduction)
    prior_tax_d = _amount("prior_cumulative_tax", prior_cumulative_tax)

    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise InputError(f"month 必须为 1-12 的整数，收到：{month!r}")
    if prior_months is None:
        months = month
    elif isinstance(prior_months, bool) or not isinstance(prior_months, int) \
            or not 0 <= prior_months <= 11:
        raise InputError(f"prior_months 必须为 0-11 的整数，收到：{prior_months!r}")
    else:
        months = prior_months + 1

    if prior_cumulative_income is None:
        prior_income = _q(income_d * (months - 1))
    else:
        prior_income = _amount("prior_cumulative_income", prior_cumulative_income)

    cumulative_income = _q(prior_income + income_d)
    cumulative_taxable = cumulative_income - (
        basic_d * months + social_d * months + special_d * months + other_d * months)
    if cumulative_taxable < 0:
        cumulative_taxable = Decimal("0.00")
    cumulative_taxable = _q(cumulative_taxable)

    rate, quick = _select_bracket(cumulative_taxable)
    quick = _q(quick)
    cumulative_tax = _q(cumulative_taxable * rate - quick)
    if cumulative_tax < 0:
        cumulative_tax = Decimal("0.00")

    tax_current = _q(cumulative_tax - prior_tax_d)
    if tax_current < 0:
        tax_current = Decimal("0.00")

    return TaxResult(
        month=month, income=income_d, social_insurance=social_d,
        special_additional=special_d, other_deduction=other_d,
        basic_deduction=basic_d, cumulative_months=months,
        cumulative_income=cumulative_income,
        cumulative_taxable_income=cumulative_taxable, tax_rate=rate,
        quick_deduction=quick, cumulative_tax=cumulative_tax,
        tax_current=tax_current,
        net_income=_q(income_d - social_d - other_d - tax_current),
    )


def format_human(result: TaxResult) -> str:
    """把结果格式化为中文人类可读明细。"""
    rate_percent = (result.tax_rate * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (
        f"个人所得税计算结果（第 {result.month} 月）\n"
        f"  税前收入：          {result.income:>12} 元\n"
        f"  专项扣除(三险一金)：{result.social_insurance:>12} 元\n"
        f"  专项附加扣除：      {result.special_additional:>12} 元\n"
        f"  其他扣除：          {result.other_deduction:>12} 元\n"
        f"  基本减除费用：      {result.basic_deduction:>12} 元\n"
        f"  扣除合计：          {result.social_insurance + result.special_additional + result.other_deduction + result.basic_deduction:>12} 元\n"
        f"  累计应纳税所得额：  {result.cumulative_taxable_income:>12} 元\n"
        f"  预扣率：            {str(rate_percent):>12}%\n"
        f"  速算扣除数：        {result.quick_deduction:>12} 元\n"
        f"  累计应预扣税额：    {result.cumulative_tax:>12} 元\n"
        f"  本期应预扣税额：    {result.tax_current:>12} 元\n"
        f"  税后收入：          {result.net_income:>12} 元"
    )


def _parse_int_in_range(name: str, text: str, low: int, high: int) -> int:
    """解析 CLI 文本为 [low, high] 内的整数。"""
    try:
        value = int(text.strip())
    except (TypeError, ValueError, AttributeError):
        raise InputError(f"参数 {name} 必须为 {low}-{high} 的整数，收到：{text}") from None
    if not low <= value <= high:
        raise InputError(f"参数 {name} 必须为 {low}-{high} 的整数，收到：{text}")
    return value


class ChineseArgumentParser(argparse.ArgumentParser):
    """把 argparse 的错误信息本地化为中文，并保持退出码 2。"""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        if message.startswith("the following arguments are required:"):
            message = "缺少必需参数 " + message.split(":", 1)[1].strip()
        elif message.startswith("unrecognized arguments:"):
            message = "无法识别的参数 " + message.split(":", 1)[1].strip()
        elif message.startswith("argument ") and message.endswith(": expected one argument"):
            flag = message[len("argument "):-len(": expected one argument")]
            message = f"参数 {flag} 缺少取值"
        sys.stderr.write(f"参数错误：{message}\n")
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器（数值参数以字符串接收，由本模块自行校验）。"""
    parser = ChineseArgumentParser(
        prog="tax_calculator.py", allow_abbrev=False,
        description="计算中国居民个人工资薪金所得的当月个人所得税（累计预扣预缴法）。")
    specs = (
        ("--income", "金额", True, None, "本月税前工资薪金收入（元），必填"),
        ("--month", "1-12", True, None, "计算所属月份，必填"),
        ("--social-insurance", "金额", False, "0", "本月专项扣除（三险一金个人部分）"),
        ("--special-additional", "金额", False, "0", "本月专项附加扣除"),
        ("--other-deduction", "金额", False, "0", "本月依法确定的其他扣除"),
        ("--prior-cumulative-tax", "金额", False, "0", "本年截至上月累计已预扣预缴税额"),
        ("--prior-cumulative-income", "金额", False, None, "本年截至上月累计收入，默认 月收入×(月份-1)"),
        ("--prior-months", "0-11", False, None, "本年已计税月数，默认 月份-1"),
        ("--basic-deduction", "金额", False, str(DEFAULT_BASIC_DEDUCTION), "每月基本减除费用"),
    )
    for flag, metavar, required, default, help_text in specs:
        parser.add_argument(flag, metavar=metavar, required=required,
                            default=default, help=help_text)
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出机器可读结果")
    return parser


def run(argv: Optional[list] = None) -> int:
    """解析参数并计算，返回退出码（0 成功 / 2 参数非法）。"""
    args = build_parser().parse_args(argv)
    try:
        prior_income = args.prior_cumulative_income
        result = calc_monthly_tax(
            income=_amount("--income", args.income),
            month=_parse_int_in_range("--month", args.month, 1, 12),
            social_insurance=_amount("--social-insurance", args.social_insurance),
            special_additional=_amount("--special-additional", args.special_additional),
            other_deduction=_amount("--other-deduction", args.other_deduction),
            prior_cumulative_tax=_amount("--prior-cumulative-tax", args.prior_cumulative_tax),
            prior_cumulative_income=(
                None if prior_income is None
                else _amount("--prior-cumulative-income", prior_income)),
            prior_months=(None if args.prior_months is None else _parse_int_in_range(
                "--prior-months", args.prior_months, 0, 11)),
            basic_deduction=_amount("--basic-deduction", args.basic_deduction),
        )
    except InputError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    if args.json:
        print(json.dumps(result.as_json_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_human(result))
    return 0


def main(argv: Optional[list] = None) -> int:
    """进程入口：捕获未预期异常并返回退出码 1（SystemExit 由 argparse 直接抛出）。"""
    try:
        return run(argv)
    except Exception as exc:  # pragma: no cover - 防御性兜底
        sys.stderr.write(f"内部错误：{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
