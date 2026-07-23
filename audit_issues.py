#!/usr/bin/env python3
"""Check duplicate files and stale data."""
import json
from pathlib import Path
from datetime import date

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = json.loads((Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
                   .read_text(encoding="utf-8")))
pool_codes = {e["code"] for e in POOL["data"]}

all_files = {fp.stem: fp for fp in HISTORY.glob("*.json") if not fp.name.startswith("_")}

# ========== Issue 1: sz-prefix duplicates ==========
print("=" * 65)
print("Issue 1: sz前缀重复文件分析")
print("=" * 65)

sz_pairs = []
for fname in sorted(all_files):
    if fname.startswith("sz"):
        base = fname[2:]
        if base in all_files:
            sz_pairs.append((base, fname))

print(f"\n发现 {len(sz_pairs)} 对重复文件")

# Compare each pair
for base, sz_name in sz_pairs:
    base_fp = all_files[base]
    sz_fp = all_files[sz_name]

    base_data = json.loads(base_fp.read_text(encoding="utf-8"))
    sz_data = json.loads(sz_fp.read_text(encoding="utf-8"))

    base_rec = base_data.get("records", [])
    sz_rec = sz_data if isinstance(sz_data, list) else sz_data.get("records", [])

    b_n, sz_n = len(base_rec), len(sz_rec)
    b_start = base_rec[0]["date"] if base_rec else "?"
    sz_start = sz_rec[0]["date"] if sz_rec else "?"
    b_end = base_rec[-1]["date"] if base_rec else "?"
    sz_end = sz_rec[-1]["date"] if sz_rec else "?"

    diff = sz_n - b_n
    is_pool = base in pool_codes

    base_fmt = "dict" if isinstance(base_data, dict) else "list"

    label = "✅池中" if is_pool else "⚠非池"
    print(f"  {base} ({label}):")
    print(f"    无前缀: {b_n}条 ({b_start} ~ {b_end})")
    print(f"    sz前缀: {sz_n}条 ({sz_start} ~ {sz_end})")
    print(f"    差异: sz多 {diff}条 ({sz_start} vs {b_start})")

pool_pairs = [p for p in sz_pairs if p[0] in pool_codes]
extra_pairs = [p for p in sz_pairs if p[0] not in pool_codes]
print(f"\n池中标的重复对: {len(pool_pairs)}")
print(f"非池遗留对:     {len(extra_pairs)}")

# ========== Issue 2: Stale data ==========
print(f"\n{'=' * 65}")
print("Issue 2: 数据过期分析")
print("=" * 65)

stale_cutoff = "2026-04-01"

stale_list = []
for e in POOL["data"]:
    code = e["code"]
    if code not in all_files:
        continue
    fp = all_files[code]
    data = json.loads(fp.read_text(encoding="utf-8"))
    rec = data.get("records", [])
    if not rec:
        continue
    last = rec[-1]["date"]
    if last < stale_cutoff:
        stale_list.append((code, e["name"], last, len(rec), rec[0]["date"]))

print(f"\n过期标的（最后更新 < {stale_cutoff}）：{len(stale_list)}只")
for code, name, last, n, start in sorted(stale_list, key=lambda x: x[2]):
    print(f"  {code} {name}: 最后{last}, {n}条 ({start} ~ {last})")

# ========== Key stale ETFs ==========
key_etfs = [s for s in stale_list if s[3] > 500]
if key_etfs:
    print(f"\n重点关注（老ETF但停在2025-12-31或更早）：")
    for code, name, last, n, start in key_etfs:
        print(f"  {code} {name}: {n}条, 停于{last}")

# ========== Coverage ==========
print(f"\n{'=' * 65}")
print("Issue 4: 覆盖深度（数据能回溯到的年份）")
print("=" * 65)

long_hist = 0
for e in POOL["data"]:
    code = e["code"]
    if code not in all_files:
        continue
    rec = json.loads(all_files[code].read_text(encoding="utf-8")).get("records", [])
    if len(rec) >= 2000:
        long_hist += 1

print(f"\n记录>=2000条的池中标的: {long_hist}只")
print(f"能回溯到2010年前后: 仅44只（按其他agent报告）")

print("\n✅ 分析完毕")
