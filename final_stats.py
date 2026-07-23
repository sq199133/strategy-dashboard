#!/usr/bin/env python3
"""Final stats."""
import json
from pathlib import Path
from collections import Counter

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = json.loads((Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
                   .read_text(encoding="utf-8")))

years = Counter()
hist_deep = Counter()
total = 0

for e in POOL["data"]:
    code = e["code"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        continue
    rec = json.loads(fp.read_text(encoding="utf-8")).get("records", [])
    if not rec:
        continue
    start = rec[0]["date"][:4]
    years[start] += 1
    n = len(rec)
    total += n
    if n >= 3500: hist_deep["3500+"] += 1
    elif n >= 3000: hist_deep["3000+"] += 1
    elif n >= 2000: hist_deep["2000+"] += 1
    elif n >= 1500: hist_deep["1500+"] += 1
    elif n >= 1000: hist_deep["1000+"] += 1
    elif n >= 500: hist_deep["500+"] += 1
    else: hist_deep["<500"] += 1

print("开始年份分布:")
for y in sorted(years):
    print(f"  {y}: {years[y]}只")

print("\n记录数分布:")
for b in ["3500+", "3000+", "2000+", "1500+", "1000+", "500+", "<500"]:
    if b in hist_deep:
        print(f"  {b}: {hist_deep[b]}只")

print(f"\n总记录: {total:,}")

# Count how many go back to 2010 or earlier
pre_2020 = sum(v for k,v in years.items() if k < "2020")
print(f"\n数据早于2020年: {pre_2020}只")
pre_2015 = sum(v for k,v in years.items() if k < "2015")
print(f"数据早于2015年: {pre_2015}只")
pre_2010 = sum(v for k,v in years.items() if k < "2010")
print(f"数据早于2010年: {pre_2010}只")
