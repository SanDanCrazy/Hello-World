# Hello-World

## 个人所得税计算脚本

```bash
python3 tax_calculator.py --income 30000 --month 1 --social-insurance 4500 --special-additional 2000
python3 tax_calculator.py --income 30000 --month 1 --json
```

测试：

```bash
python3 -m unittest discover -s tests -v
```

说明：按 2019 年起居民个人工资薪金所得累计预扣预缴法计算；不做年度汇算清缴，负税额按 0 计。
