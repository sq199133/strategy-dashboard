#!/usr/bin/env python3
"""
Fix ETF data issues:
1. Re-download 20 ETFs with <100 records
2. Fix date sort errors on 2 ETFs
"""
import json, os, datetime, sys
from pathlib import Path

HISTORY_DIR = Path("D:/QClaw_Trading/data/history")
POOL_FILE = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

with open(POOL_FILE, encoding="utf-8") as f:
    pool = json.load(f)
etf_map = {e["code"]: e for e in pool["data"]}

# ===== 1. Re-download ETFs with <100 records =====
short_codes = [
    "560700", "512330", "510180", "513360", "562800", "561380",
    "512040", "517330", "516520", "560120", "515760", "560710",
    "512880", "560160", "513400", "513850",
]

print("=== Re-downloading short-record ETFs ===")
try:
    import akshare as ak
    
    success = 0
    for code in short_codes:
        name = etf_map.get(code, {}).get("name", "?")
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                     start_date="20000101", end_date="20270101", adjust="qfq")
            if df is not None and len(df) > 0:
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "date": str(row["日期"]),
                        "open": float(row["开盘"]),
                        "close": float(row["收盘"]),
                        "high": float(row["最高"]),
                        "low": float(row["最低"]),
                        "vol": int(float(row.get("成交量", 0))),
                        "amount": int(float(row.get("成交额", 0))),
                        "chg": float(row.get("涨跌幅", 0))
                    })
                records.sort(key=lambda r: r["date"])
                out = {"code": code, "name": name, "records": records}
                with open(HISTORY_DIR / f"{code}.json", "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False)
                print(f"  ✓ {code} {name}: {len(records)} records")
                success += 1
            else:
                print(f"  ✗ {code} {name}: 0 records returned")
        except Exception as e:
            print(f"  ✗ {code} {name}: {e}")
    
    print(f"\nRe-downloaded: {success}/{len(short_codes)}")
except ImportError:
    print("akshare not available")

# ===== 2. Fix date sort errors =====
print("\n=== Fixing date sort errors ===")
fix_codes = ["159918", "510500"]
for code in fix_codes:
    fp = HISTORY_DIR / f"{code}.json"
    if not fp.exists():
        print(f"  - {code}: file not found")
        continue
    name = etf_map.get(code, {}).get("name", "?")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        records = data if isinstance(data, list) else data.get("records", [])
        
        # If it's a list (bare array), wrap it
        if isinstance(data, list):
            # Check date format - some might have unparsable dates
            for r in records:
                d = r.get("date", "")
                # Fix common date issues: e.g. "20230101" -> "2023-01-01"
                if isinstance(d, str) and len(d) == 8 and d.isdigit():
                    r["date"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            
            records.sort(key=lambda r: r["date"])
            out = {"code": code, "name": name, "records": records}
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False)
            print(f"  ✓ {code} {name}: fixed, {len(records)} records")
        else:
            print(f"  - {code} {name}: already dict format, checking dates")
            # Just resort
            records.sort(key=lambda r: r["date"])
            data["records"] = records
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"  ✓ {code} {name}: re-sorted, {len(records)} records")
    except Exception as e:
        print(f"  ✗ {code} {name}: {e}")

print("\n=== Done ===")

# ===== 3. Final summary =====
print("\n" + "=" * 50)
print("FINAL REPORT")
print("=" * 50)

all_files = list(HISTORY_DIR.glob("*.json"))
total = len(all_files)
pool_present = sum(1 for c in etf_map if (HISTORY_DIR / f"{c}.json").exists())

print(f"Total JSON files: {total}")
print(f"Pool ETFs present: {pool_present}/{len(etf_map)}")

# Remaining issues
remaining_short = []
for fp in all_files:
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        records = data.get("records", [])
        if len(records) < 50:
            remaining_short.append((fp.stem, len(records)))
    except:
        pass

if remaining_short:
    print(f"\n⚠ Still short (<50 records):")
    for code, n in sorted(remaining_short, key=lambda x: x[1]):
        name = etf_map.get(code, {}).get("name", "?")
        print(f"  {code} {name}: {n}")
else:
    print(f"\n✅ All ETFs have adequate records")
