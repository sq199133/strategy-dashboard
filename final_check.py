#!/usr/bin/env python3
"""Final data quality check - handles both dict and list formats."""
import json
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

def get_records(fp):
    data = json.loads(fp.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("records", [])
    elif isinstance(data, list):
        return data
    return []

# Coverage check
all_files = {fp.stem for fp in HISTORY.glob("*.json")}
pool_missing = [c for c in etf_map if c not in all_files]
pool_present = len(etf_map) - len(pool_missing)

print(f"Pool ETFs: {len(etf_map)}")
print(f"Present:   {pool_present}")
print(f"Missing:   {len(pool_missing)}")
if pool_missing:
    for c in pool_missing:
        print(f"  {c} {etf_map.get(c,{}).get('name','?')}")

# Record count distribution
pool_files = {c: HISTORY / f"{c}.json" for c in etf_map if (HISTORY / f"{c}.json").exists()}
counts = {}
for code, fp in pool_files.items():
    records = get_records(fp)
    counts[code] = len(records)

# Sort and show bottom
print(f"\n=== Bottom 20 by record count ===")
for code, cnt in sorted(counts.items(), key=lambda x: x[1])[:20]:
    name = etf_map[code]["name"]
    fp = HISTORY / f"{code}.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    fmt = "dict" if isinstance(data, dict) else "list"
    start = get_records(fp)[0].get("date", "?") if get_records(fp) else "?"
    print(f"  {code} {name}: {cnt} rec ({fmt}, {start} ~ )")

# Format distribution
dict_count = 0
list_count = 0
for code, fp in pool_files.items():
    data = json.loads(fp.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        dict_count += 1
    else:
        list_count += 1

print(f"\nFormat: dict={dict_count}, list={list_count}")

# Check for <50 records
short = [(c, n) for c, n in counts.items() if n < 50]
print(f"\nSHORT (<50 rec): {len(short)}")
for code, cnt in sorted(short, key=lambda x: x[1]):
    name = etf_map.get(code, {}).get("name", "?")
    print(f"  {code} {name}: {cnt}")

# Data structure check for all files
print(f"\n=== Data structure spot-check ===")
for code in sorted(etf_map)[:5]:
    fp = HISTORY / f"{code}.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("records", [])
    r0 = records[0] if records else {}
    print(f"  {code}: type={type(data).__name__}, {len(records)} rec, keys={list(r0.keys())[:6]}")

print("\nDone.")
