# Hello-World

## 年度节假日时长统计脚本

`holiday_stats.py` 是一个纯标准库、可离线运行的 Python 3.9+ 命令行工具，按年度统计中国大陆法定节假日的放假安排与时长。

### 环境要求

- Python 3.9 及以上
- 无第三方依赖，无需联网

### 运行方式

```bash
# 单年查询（默认表格输出）
python holiday_stats.py --year 2025

# 多年查询（--year 可重复，也可逗号分隔，输出按年份升序）
python holiday_stats.py --year 2024 --year 2025
python holiday_stats.py --year 2024,2025

# 全量查询
python holiday_stats.py --all

# JSON 输出
python holiday_stats.py --year 2025 --format json

# 使用自定义数据文件
python holiday_stats.py --year 2025 --data ./my_holidays.json

# 帮助
python holiday_stats.py --help
```

`--year` 与 `--all` 互斥；未提供任何查询参数时会打印帮助并以退出码 1 结束。

### 输出示例

```
== 2025 年 ==
节日           开始日期    结束日期    放假天数  法定天数
元旦           2025-01-01  2025-01-01         1         1
春节           2025-01-28  2025-02-04         8         4
清明节         2025-04-04  2025-04-06         3         1
劳动节         2025-05-01  2025-05-05         5         2
端午节         2025-05-31  2025-06-02         3         1
国庆节/中秋节  2025-10-01  2025-10-08         8         4
小计：放假 28 天 | 法定 13 天 | 调休上班 5 天 | 净休息 23 天
```

JSON 输出（`--format json`）结构稳定，顶层固定为 `{"country": "CN", "years": [...]}`，每个年度包含 `year`、`source`、`holidays` 明细数组与 `summary` 汇总对象，便于程序消费。

### 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 参数错误（缺参、互斥参数同时使用、年份格式非法等） |
| 2 | 请求年份无数据（会列出已支持年份） |
| 3 | 数据文件缺失、不可读或校验失败 |

错误信息统一输出到 stderr，不会打印 Python traceback。

### 数据文件

默认数据文件为 `data/cn_holidays.json`（相对脚本所在目录解析，与当前工作目录无关）。结构如下：

```json
{
  "country": "CN",
  "years": {
    "2025": {
      "source": "国务院办公厅关于2025年部分节假日安排的通知",
      "holidays": [
        {"name": "元旦", "start": "2025-01-01", "end": "2025-01-01", "statutory_days": 1}
      ],
      "makeup_workdays": ["2025-01-26"]
    }
  }
}
```

约束：

- `years` 对象的键为四位年份字符串，每个年度的 `holidays` 为非空数组。
- `name`、`start`、`end`、`statutory_days` 必填；日期使用 `YYYY-MM-DD`。
- `end >= start`；`statutory_days` 为整数且不超过放假天数。
- `makeup_workdays` 为日期数组（可为空），不得落在本年度任一放假区间内。
- 节日起始日期必须属于其所属年份（跨年节日归属起始年）。
- 数据文件必须保存为 UTF-8 编码（不支持 GBK/GB2312 等，暂不支持 UTF-8 BOM）。
- 节日与 `makeup_workdays` 条目请勿重复填写；脚本按条目原样统计，不做去重。

#### 新增年度

1. 在 `data/cn_holidays.json` 的 `years` 下追加新的年份键。
2. 按国务院办公厅当年通知录入节日与调休上班日。
3. 运行 `python holiday_stats.py --year <新年份>` 确认输出，并执行 `python -m unittest discover -s tests -v`。

无需修改代码；未录入的年份会返回退出码 2，脚本不会推算未公布年度。

### 统计口径

- **放假天数**：`结束日期 - 开始日期 + 1` 的自然日天数，包含其中的周末与调休连休。
- **法定节假日天数**：来自数据文件 `statutory_days`，仅统计法定部分，不含周末与调休借休。
- **调休上班天数**：年度内被调整为工作日的周末天数，按年度汇总。
- **年度放假总天数**：该年度所有节日放假天数之和。
- **净休息天数**（辅助指标）：放假总天数 − 调休上班天数，可能为负，仅作参考。
- 跨年节日按放假起始日期所在年度归属；日期不带时区信息。

数据以官方通知最终执行版本为准，节假日安排发布后请及时更新数据文件。

### 测试

```bash
python -m py_compile holiday_stats.py
python -m unittest discover -s tests -v
```