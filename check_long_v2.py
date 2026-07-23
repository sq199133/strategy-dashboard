#!/usr/bin/env python3
"""Check history_long_v2 directory."""
import json
from pathlib import Path
from collections import Counter

p = Path("D:/QClaw_Trading/data/history_long_v2")
files = sorted(p.glob("*.json"))
print(f"文件数: {len(files)}个")

# Check format
f0 = files[0]
d = json.loads(f0.read_text(encoding="utf-8"))
print(f"\n=== 格式检查 ({f0.name}) ===")
print(f"顶层类型: {type(d).__name__}")
print(f"顶层键: {list(d.keys()) if isinstance(d, dict) else 'list'}")

if isinstance(d, dict):
    recs = d.get("records", d.get("data", []))
elif isinstance(d, list):
    recs = d
else:
    recs = []

if recs:
    if isinstance(recs[0], dict):
        print(f"字段: {list(recs[0].keys())}")
        print(f"首条: {recs[0]}")
        print(f"末条: {recs[-1]}")
        print(f"日期跨度: {recs[0].get('date','?')} ~ {recs[-1].get('date','?')}")
    elif isinstance(recs[0], list):
        print(f"数组格式: {recs[0]}")
        print(f"末条: {recs[-1]}")

# Full survey: count records per file, overlap with pool
q_pool = json.loads((Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
                     .read_text(encoding="utf-8")))
pool_codes = {e["code"] for e in q_pool["data"]}

print(f"\n=== 与标的池重叠 ===")
pool_match = 0
hist_dir = Path("D:/QClaw_Trading/data/history")
for fp in files:
    code = fp.stem
    is_pool = code in pool_codes
    is_exist = (hist_dir / f"{code}.json").exists()
    if is_pool and is_exist:
        pool_match += 1
        
print(f"池中标的（同时存在于history/）: {pool_match}只")

# Check field overlap between history_long_v2 and history
if recs and isinstance(recs[0], dict):
    long_v2_keys = set(recs[0].keys())
    hist_rec = json.loads((hist_dir / f"{f0.stem}.json").read_text(encoding="utf-8"))["records"][0]
    hist_keys = set(hist_rec.keys())
    common = long_v2_keys & hist_keys
    only_long = long_v2_keys - hist_keys
    only_hist = hist_keys - long_v2_keys
    print(f"\n=== 字段对比 ===")
    print(f"共有字段: {common}")
    print(f"long_v2独有: {only_long}")
    print(f"history独有: {only_hist}")

# Check pool coverage
pool_codes_set = pool_codes
in_v2 = [f.stem for f in files if f.stem in pool_codes_set]
not_in_v2 = pool_codes_set - {f.stem for f in files}
print(f"\n池195只 → long_v2中有: {len(in_v2)}只")
print(f"池195只 → long_v2缺失: {len(not_in_v2)}只 ({sorted(not_in_v2)[:10]}...)")

# Record count stats
record_counts = []
for fp in files:
    d = json.loads(fp.read_text(encoding="utf-8"))
    if isinstance(d, dict):
        r = d.get("records", d.get("data", []))
    elif isinstance(d, list):
        r = d
    else:
        r = []
    if r:
        start = r[0].get("date","?") if isinstance(r[0], dict) else r[0][0]
        end = r[-1].get("date","?") if isinstance(r[-1], dict) else r[-1][0]
        record_counts.append((fp.stem, len(r), start, end))

print(f"\n=== 周线记录统计 ===")
n = len(record_counts)
counts = sorted([c for _,c,_,_ in record_counts])
import statistics
print(f"总行数: {sum(counts):,}")
print(f"均值: {statistics.mean(counts):.0f}")
print(f"中位数: {statistics.median(counts):.0f}")
print(f"P25: {counts[n//4]:.0f}")
print(f"P75: {counts[n*3//4]:.0f}")
print(f"最小: {min(counts)} ({(min(record_counts, key=lambda x:x[1])[0])})")
print(f"最大: {max(counts)} ({(max(record_counts, key=lambda x:x[1])[0])})")

# Show earliest/latest dates
starts = sorted(set(s for _,_,s,_ in record_counts))
ends = sorted(set(e for _,_,_,e in record_counts))
print(f"日期范围: {starts[0]} ~ {ends[-1]}")
