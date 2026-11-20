# 星座计算程序（zodiac）

一个离线、零第三方依赖的 Python 程序，输入**公历**或**农历（含闰月）**生日即可得到西洋十二**太阳星座**。
同时提供可复用的库 API 与命令行入口 `python -m zodiac`。

## 环境要求

- Python 3.8+
- 仅使用标准库，无需 `pip install`，运行期零网络访问
- 所有命令在仓库根目录（本 README 所在目录）执行

## 命令行用法

```bash
# 公历（默认）
python -m zodiac --date 1990-08-15

# 农历正月初一
python -m zodiac --calendar lunar --date 2024-01-01

# 农历闰二月初一
python -m zodiac --calendar lunar --date 2023-02-01 --leap

# 单行 JSON 输出
python -m zodiac --calendar lunar --date 2023-02-01 --leap --json

# 帮助
python -m zodiac --help
```

参数：

| 参数 | 说明 |
| --- | --- |
| `--calendar {solar,lunar}` | 输入历法，默认 `solar`（公历） |
| `--date YYYY-MM-DD` | 必填；农历时按月/日解释农历年月日 |
| `--leap` | 仅农历有效，表示该月为闰月 |
| `--json` | 输出单行 JSON |

人类可读输出示例：

```
公历: 2024-02-10
农历: 农历二〇二四年正月初一
星座: 水瓶座 (Aquarius)
```

JSON 输出示例：

```json
{"input_calendar":"lunar","solar_date":"2024-02-10","lunar_year":2024,"lunar_month":1,"lunar_day":1,"is_leap_month":false,"lunar_text":"农历二〇二四年正月初一","sign_zh":"水瓶座","sign_en":"Aquarius"}
```

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 未预期的内部错误（不会输出伪结果） |
| `2` | 参数错误、日期不存在（含非法闰月、大小月不存在） |
| `3` | 日期超出支持范围 |

## 库 API

```python
from zodiac import get_zodiac, lunar_to_solar, solar_to_lunar, ZodiacResult

get_zodiac(1990, 8, 15)                                    # 公历 -> 狮子座
get_zodiac(2024, 1, 1, calendar="lunar")                   # 农历正月初一 -> 水瓶座
get_zodiac(2023, 2, 1, calendar="lunar", is_leap_month=True)  # 闰二月初一 -> 白羊座

lunar_to_solar(2024, 1, 1)                                 # date(2024, 2, 10)
solar_to_lunar(__import__("datetime").date(2024, 2, 10))   # LunarDate(year=2024, month=1, day=1, ...)
```

`get_zodiac` 返回不可变的 `ZodiacResult`（`@dataclass(frozen=True)`），字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sign_zh` | str | 星座中文名 |
| `sign_en` | str | 星座英文名 |
| `solar_date` | date | 对应公历日期 |
| `lunar_year` / `lunar_month` / `lunar_day` | int | 农历年月日 |
| `is_leap_month` | bool | 该农历月是否闰月 |
| `lunar_text` | str | 农历可读文本 |
| `input_calendar` | str | `solar` 或 `lunar` |

错误以异常表达：`InvalidDateError`、`OutOfRangeError`，两者均继承 `ValueError`。
`calendar` 仅接受 `"solar"` / `"lunar"`，其他值抛 `ValueError`。
`import zodiac` 不打印、不联网、不读写文件。

## 星座边界口径

采用通行的**固定日期边界表**（不按节气瞬时或真太阳黄经计算）：

| 星座 | 英文 | 起始（含） | 结束（含） |
| --- | --- | --- | --- |
| 白羊座 | Aries | 03-21 | 04-19 |
| 金牛座 | Taurus | 04-20 | 05-20 |
| 双子座 | Gemini | 05-21 | 06-21 |
| 巨蟹座 | Cancer | 06-22 | 07-22 |
| 狮子座 | Leo | 07-23 | 08-22 |
| 处女座 | Virgo | 08-23 | 09-22 |
| 天秤座 | Libra | 09-23 | 10-23 |
| 天蝎座 | Scorpio | 10-24 | 11-22 |
| 射手座 | Sagittarius | 11-23 | 12-21 |
| 摩羯座 | Capricorn | 12-22 | 次年 01-19 |
| 水瓶座 | Aquarius | 01-20 | 02-18 |
| 双鱼座 | Pisces | 02-19 | 03-20 |

## 支持范围与已知限制

- 内置农历数据表覆盖农历 **1900–2100** 年（春节锚点、月大小、闰月位置）。
- **农历生日查询**（`get_zodiac(..., calendar="lunar")`）只接受农历 **1900–2099** 年；超出报 `OutOfRangeError`。
- **公历查询 / `solar_to_lunar`** 接受 `1900-01-31` ~ `2100-12-31`。
- `lunar_to_solar` 覆盖数据表全范围（农历 1900–2100），以便公历端日期可完整回环。
- 不处理时辰、子时换日、真太阳时、时区；仅按日期计算。
- 不做天文星座、上升/月亮星座、生肖、八字、节气。
- 不处理 1582 年改历前历史日期。

> 说明：农历生日输入上限为 2099 年（需求 FR-7），而公历上限为 `2100-12-31`（由数据表推导），
> 因此农历 2100 年只可能出现在“公历 → 农历”的输出中。

## 数据来源

农历数据使用通行的标准农历打包表（与 calendar.js 等主流实现一致），
并以内置锚点测试锁定：春节（1900-01-31、1949-01-29、1984-02-02、2000-02-05、
2020-01-25、2023-01-22、2024-02-10、2033-01-31、2034-02-19 等）以及
2020 闰四月（2020-05-23）、2023 闰二月（2023-03-22）、2033 闰十一月（2033-12-22）。

## 测试

```bash
python -m unittest discover -s tests -v
```

测试离线运行，覆盖星座边界逐日校验、农历闰月锚点、公历↔农历全范围回环、
异常类型、CLI 退出码与 JSON 输出，无跳过用例。