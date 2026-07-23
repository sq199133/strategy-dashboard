#!/usr/bin/env python3
"""Check start dates of all pool ETFs."""
import json
from pathlib import Path
from collections import Counter

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

# Gather start dates
year_counts = Counter()
year2etfs = {}

for e in pool["data"]:
    code = e["code"]
    name = e["name"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        continue
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data.get("records", [])
    if not records:
        continue
    start_date = records[0]["date"]
    year = start_date[:4]
    year_counts[year] += 1
    if year not in year2etfs:
        year2etfs[year] = []
    year2etfs[year].append((code, name, start_date, len(records)))

print("ETF 数据开始年份分布：")
print(f"{'年份':>6} | {'数量':>6} | {'占比':>6}")
print("-" * 25)
for year in sorted(year_counts):
    pct = year_counts[year] / len(pool) * 100
    print(f"{year:>6} | {year_counts[year]:>6} | {pct:>5.1f}%")

print(f"\n总计: {sum(year_counts.values())} 只")

# Show 2025+ in detail
print("\n=== 2025年及以后开始的ETF ===")
for year in sorted(y for y in year2etfs if int(y) >= 2025):
    etfs = sorted(year2etfs[year], key=lambda x: x[2])
    print(f"\n--- {year}年（{len(etfs)}只）---")
    for code, name, start, n in etfs:
        print(f"  {code} {name}: {start} ~ ({n}条)")

# Also check: how many of the 2025+ ETFs have issue_date info in the pool?
print("\n=== 2025+ ETFs 的发行日期对照 ===")
for year in sorted(y for y in year2etfs if int(y) >= 2025):
    for code, name, start, n in sorted(year2etfs[year], key=lambda x: x[2]):
        e = etf_map.get(code, {})
        issue = e.get("issue_date", e.get("listing_date", "?"))
        print(f"  {code} {name}: 数据起始={start}, 发行={issue}")
