#!/usr/bin/env python3
"""Merge better sz-prefix data into non-prefix files."""
import json
from pathlib import Path
from datetime import date

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = json.loads((Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
                   .read_text(encoding="utf-8")))
etf_map = {e["code"]: e for e in POOL["data"]}

# 15 pairs where sz version is clearly better (500+ more records)
merge_list = [
    "160125", "160140", "160216", "160416", "160719",
    "161116", "161128", "161129", "161130", "161815",
    "162411", "162719", "163208", "164701", "165513",
    # vs. 差异微小的:
    # 160644 (base -191), 160723 (-21), 161126 (-34), 161127 (-21)
    # 162415 (-10), 501225 (-1), 501312 (0)
    # 164824 (sz多339条 - 差异不大，保留base)
]

# 164824 is borderline (sz has 339 more, but starts 2018 vs 2020)
# Let's include it too since it's signifiantly more data
merge_list.append("164824")

converted = 0
for code in merge_list:
    base_fp = HISTORY / f"{code}.json"
    sz_fp = HISTORY / f"sz{code}.json"
    
    if not sz_fp.exists():
        print(f"  {code}: sz文件不存在，跳过")
        continue
    
    sz_data = json.loads(sz_fp.read_text(encoding="utf-8"))
    
    # Handle both list and dict format
    if isinstance(sz_data, list):
        # Determine mapping from first record keys
        recs = []
        for r in sz_data:
            recs.append({
                "date": r.get("date") or r.get("day", ""),
                "open": float(r.get("open", 0)),
                "close": float(r.get("close", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "vol": int(float(r.get("vol") or r.get("volume", 0))),
                "amount": int(float(r.get("amount", 0))),
                "chg": float(r.get("chg", 0)),
            })
    else:
        recs = sz_data.get("records", [])
        # Ensure all fields
        cleaned = []
        for r in recs:
            cleaned.append({
                "date": r.get("date", ""),
                "open": float(r.get("open", 0)),
                "close": float(r.get("close", 0)),
                "high": float(r.get("high", 0)),
                "low": float(r.get("low", 0)),
                "vol": int(float(r.get("vol", 0))),
                "amount": int(float(r.get("amount", 0))),
                "chg": float(r.get("chg", 0)),
            })
        recs = cleaned
    
    recs.sort(key=lambda r: r["date"])
    name = etf_map.get(code, {}).get("name", code)
    
    out = {"code": code, "name": name, "records": recs}
    base_fp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    
    print(f"  {code} {name}: sz → base ({len(recs)}条, {recs[0]['date']}~{recs[-1]['date']})")
    converted += 1

# Remove sz-prefix files that have been merged
print(f"\n合并完成: {converted}只")
print("清理sz前缀文件...")
for code in merge_list:
    sz_fp = HISTORY / f"sz{code}.json"
    if sz_fp.exists():
        sz_fp.unlink()
        print(f"  已删: sz{code}.json")

# Final verification
print(f"\n{'=' * 50}")
print("最终状态验证")
print(f"{'=' * 50}")

sz_left = list(HISTORY.glob("sz*.json"))
print(f"剩余sz前缀文件: {len(sz_left)}个")
for f in sorted(sz_left):
    print(f"  {f.name}")

# Also double-check the new record counts
print(f"\n合并后记录数:")
for code in merge_list:
    fp = HISTORY / f"{code}.json"
    if fp.exists():
        d = json.loads(fp.read_text(encoding="utf-8"))
        r = d["records"]
        print(f"  {code}: {len(r)}条 ({r[0]['date']}~{r[-1]['date']})")
