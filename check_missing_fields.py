#!/usr/bin/env python3
"""Check all pool ETFs for missing high/low/open/vol/amount fields."""
import json
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]

print(f"扫描 {len(pool)} 只ETF，检查缺失字段...\n")

issues = []
field_stats = {"open": 0, "high": 0, "low": 0, "vol": 0, "amount": 0, "chg": 0}
field_missing_pct = {}

for e in pool:
    code = e["code"]
    name = e.get("name", "")
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        issues.append((code, name, "FILE_MISS", "文件不存在"))
        continue
    
    raw = json.loads(fp.read_text(encoding="utf-8"))
    records = raw.get("records", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    
    if not records:
        issues.append((code, name, "EMPTY", "空记录"))
        continue
    
    # Check first record for available fields
    first = records[0]
    available = set(first.keys())
    
    # Check all records for each field
    missing_any = {}
    for field in ["open", "high", "low", "vol", "amount", "chg"]:
        missing_cnt = sum(1 for r in records if field not in r)
        if missing_cnt > 0:
            missing_any[field] = missing_cnt
    
    if missing_any:
        details = "; ".join(f"{f}缺{missing_cnt}条" for f, missing_cnt in sorted(missing_any.items()))
        issues.append((code, name, "FIELD_MISS", details))
    
    # Count field presence in first record for summary
    for field in ["open", "high", "low", "vol", "amount", "chg"]:
        if field in first:
            field_stats[field] += 1

# === Output ===
print(f"=== 字段覆盖率（195只ETF）===")
for field, cnt in sorted(field_stats.items()):
    print(f"  {field}: {cnt}/{len(pool)} ({(cnt/len(pool))*100:.0f}%)")

print()

# Group issues by type
field_miss = [x for x in issues if x[2] == "FIELD_MISS"]
file_miss = [x for x in issues if x[2] == "FILE_MISS"]
empty = [x for x in issues if x[2] == "EMPTY"]

if file_miss:
    print(f"=== 文件缺失 ({len(file_miss)}) ===")
    for code, name, _, desc in file_miss:
        print(f"  {code} {name}")

if empty:
    print(f"\n=== 空记录 ({len(empty)}) ===")
    for code, name, _, desc in empty:
        print(f"  {code} {name}")

if field_miss:
    print(f"\n=== 字段缺失 ({len(field_miss)}) ===")
    for code, name, _, details in field_miss:
        print(f"  {code} {name[:20]:<20s} {details}")
    
    # Detail: show max missing percentage
    print(f"\n=== 详细缺失比例 ===")
    for code, name, _, details in field_miss:
        fp = HISTORY / f"{code}.json"
        raw = json.loads(fp.read_text(encoding="utf-8"))
        records = raw.get("records", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        n = len(records)
        percents = []
        for part in details.split("; "):
            fname, cnt_str = part.split("缺")
            cnt = int(cnt_str.replace("条", ""))
            percents.append(f"{fname}缺{cnt}/{n}({cnt/n*100:.0f}%)")
        print(f"  {code} {name[:20]:<20s} {'; '.join(percents)}")
else:
    print("✅ 所有标的字段完整！")

# Also check non-pool files quickly
print(f"\n=== 非池标文件快速扫描 ===")
pool_codes = {e["code"] for e in pool}
all_files = sorted([fp for fp in sorted(HISTORY.glob("*.json")) if fp.stem not in pool_codes])
if all_files:
    for fp in all_files:
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            recs = raw.get("records", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
            if recs:
                first = recs[0]
                missing = [f for f in ["open", "high", "low", "vol"] if f not in first]
                if missing:
                    print(f"  {fp.stem}: 缺{', '.join(missing)}")
        except:
            pass
    print(f"  检查{len(all_files)}个非池标文件完成")
else:
    print("  无非池标文件")
