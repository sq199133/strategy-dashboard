#!/usr/bin/env python3
"""Fix all ETF data issues."""
import json, time, random, sys
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

# ========== 1. Fix date sort errors ==========
print("=== Fixing 159918 & 510500 ===")
for code in ["159918", "510500"]:
    fp = HISTORY / f"{code}.json"
    raw = json.loads(fp.read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else raw.get("records", [])
    
    if records and "day" in records[0] and "date" not in records[0]:
        for r in records:
            r["date"] = str(r["day"])
            r["vol"] = int(float(r.get("volume", 0)))
            r["amount"] = 0
            r["chg"] = 0.0
            # Convert string prices to float
            for k in ["open", "high", "low", "close"]:
                v = r.get(k)
                if isinstance(v, str):
                    r[k] = float(v)
    
    records.sort(key=lambda r: str(r.get("date", "")))
    out = {"code": code, "name": etf_map.get(code, {}).get("name", "?"), "records": records}
    fp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ {code}: {len(records)} records fixed")

# ========== 2. Re-download short ETFs ==========
short_codes = [
    "560700", "512330", "510180", "513360", "562800", "561380",
    "512040", "517330", "516520", "560120", "515760", "560710",
    "512880", "560160", "513400", "513850",
]

import akshare as ak

print("\n=== Re-downloading short ETFs ===")
success = 0
for i, code in enumerate(short_codes):
    name = etf_map.get(code, {}).get("name", "?")
    print(f"  [{i+1}/{len(short_codes)}] {code} {name}...", end=" ", flush=True)
    
    for attempt in range(3):
        try:
            time.sleep(2.5 + random.random() * 3)
            df = ak.fund_etf_hist_em(symbol=code, period="daily",
                                     start_date="20000101", end_date="20270101", adjust="qfq")
            if df is not None and len(df) > 10:
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
                fp = HISTORY / f"{code}.json"
                fp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                print(f"✓ {len(records)} records")
                success += 1
                break
            else:
                print(f"✗(0rec) ", end="")
        except Exception as e:
            err = str(e).split("\n")[0][:60]
            print(f"✗({err}) ", end="")
        time.sleep(1)
    else:
        print()

print(f"\nDownloaded: {success}/{len(short_codes)}")

# ========== 3. Final scan ==========
print("\n" + "=" * 55)
print("FINAL QUALITY CHECK")
print("=" * 55)

issues = []
for e in pool["data"]:
    code = e["code"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        issues.append((code, "MISSING"))
        continue
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        records = data.get("records", []) if isinstance(data, dict) else data
    except:
        issues.append((code, "PARSE_ERROR"))
        continue
    if not records:
        issues.append((code, "EMPTY"))
        continue
    if len(records) < 50:
        issues.append((code, f"SHORT({len(records)})"))

print(f"Total pool ETFs: {len(pool['data'])}")
all_exist = all((HISTORY / f'{e["code"]}.json').exists() for e in pool['data'])
print(f"All files exist: {all_exist}")

if issues:
    print(f"\n⚠ Remaining issues ({len(issues)}):")
    for code, desc in sorted(issues):
        name = etf_map.get(code, {}).get("name", "?")
        print(f"  {code} {name}: {desc}")
else:
    print("\n✅ All 195 ETFs have good data!")

print("\n=== Done ===")
