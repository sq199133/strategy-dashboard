#!/usr/bin/env python3
"""
Check ALL pool ETFs for data completeness & anomalies.
Handle multiple data formats.
"""
import json, os, datetime, sys
from pathlib import Path
from collections import Counter, defaultdict

HISTORY_DIR = Path("D:/QClaw_Trading/data/history")
POOL_FILE = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
ENCODINGS = ['utf-8', 'gbk', 'gb18030', 'utf-16']

def load_json_safe(fp):
    for enc in ENCODINGS:
        try:
            with open(fp, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"Cannot decode {fp}")

with open(POOL_FILE, encoding="utf-8") as f:
    pool = json.load(f)
etfs = pool["data"]
expected = {e["code"]: e for e in etfs}
print(f"Pool size: {len(expected)} ETFs/LOFs")

# Check coverage
existing = {fp.stem for fp in HISTORY_DIR.glob("*.json")}
pool_present = sum(1 for c in expected if c in existing)
pool_missing = [c for c in expected if c not in existing]
print(f"Pool ETFs present: {pool_present}/{len(expected)}")
if pool_missing:
    print(f"\n** STILL MISSING ({len(pool_missing)}): **")
    for c in pool_missing:
        e = expected[c]
        print(f"  {c} {e['name']} [{e.get('category','?')}]")

# Quality check
print("\n" + "=" * 70)
print("DATA QUALITY CHECK")
print("=" * 70)

issues = []
record_info = []
today = datetime.date.today()

for e in etfs:
    code = e["code"]
    name = e["name"]
    fp = HISTORY_DIR / f"{code}.json"
    if not fp.exists():
        issues.append((code, "MISSING_FILE"))
        continue
    
    try:
        data = load_json_safe(fp)
    except Exception as ex:
        issues.append((code, f"LOAD_ERROR: {ex}"))
        continue
    
    # Normalize to list of records
    raw_records = None
    if isinstance(data, dict):
        raw_records = data.get("records", [])
    elif isinstance(data, list):
        raw_records = data
    else:
        issues.append((code, f"UNKNOWN_TYPE: {type(data)}"))
        continue
    
    if not raw_records:
        issues.append((code, "EMPTY: 0 records"))
        continue
    
    # Normalize each record to a dict with date + price fields
    records = []
    for r in raw_records:
        if not isinstance(r, dict):
            continue
        rec = {"date": r.get("date", "unknown")}
        # Map various field names
        rec["open"] = r.get("open", r.get("close", 0))
        rec["close"] = r.get("close", r.get("close", 0))
        rec["high"] = r.get("high", r.get("close", 0))
        rec["low"] = r.get("low", r.get("close", 0))
        rec["vol"] = r.get("vol", r.get("volume", 0))
        rec["amount"] = r.get("amount", r.get("amount", 0))
        records.append(rec)
    
    # Sort by date
    try:
        records.sort(key=lambda r: r["date"])
    except:
        issues.append((code, "DATE_SORT_ERR"))
        continue
    
    n = len(records)
    dates = [r["date"] for r in records]
    start_date = dates[0]
    end_date = dates[-1]
    record_info.append((code, name, n, start_date, end_date,
                        "open" in raw_records[0] if raw_records and isinstance(raw_records[0], dict) else False))
    
    issue_list = []
    
    # 1. Duplicate dates
    if len(dates) != len(set(dates)):
        dupes = {d: c for d, c in Counter(dates).items() if c > 1}
        issue_list.append(f"DUP_DATE:{len(dupes)}")
    
    # 2. Date gaps (>10 calendar days)
    gap_count = 0
    gap_ex = []
    for i in range(1, n):
        try:
            d1 = datetime.date.fromisoformat(dates[i-1])
            d2 = datetime.date.fromisoformat(dates[i])
            diff = (d2 - d1).days
            if diff > 10:
                gap_count += 1
                if len(gap_ex) < 3:
                    gap_ex.append(f"{dates[i-1]}→{dates[i]}({diff}d)")
        except:
            pass
    if gap_count > 0:
        issue_list.append(f"GAP>{gap_count} ({'; '.join(gap_ex[:3])})")
    
    # 3. Price anomaly (only if has full price data)
    def safe_float(v):
        try: return float(v)
        except: return 0.0
    keys = set(raw_records[0].keys()) if raw_records and isinstance(raw_records[0], dict) else set()
    if 'open' in keys and 'high' in keys and 'low' in keys:
        anom = 0
        for r in raw_records:
            o = safe_float(r.get("open",0))
            cc = safe_float(r.get("close",0))
            h = safe_float(r.get("high",0))
            l = safe_float(r.get("low",0))
            if any(v <= 0 for v in [o, cc, h, l]):
                anom += 1
            elif h < max(o, cc) or h < l or l > min(o, cc) or l > h:
                anom += 1
        if anom:
            issue_list.append(f"PRICE_ANOMALY:{anom}")
    
    # 4. Zero volume (only if vol field exists)
    if 'vol' in keys:
        zvol = sum(1 for r in raw_records if r.get("vol", 0) == 0)
        if zvol > n * 0.8:
            issue_list.append(f"NO_VOL:{zvol}/{n}")
    
    # 5. Too few records
    if n < 100:
        issue_list.append(f"FEW:{n}")
    
    # 6. Stale data
    try:
        lst = datetime.date.fromisoformat(end_date)
        stale = (today - lst).days
        if stale > 30:
            issue_list.append(f"STALE({stale}d)")
    except:
        pass
    
    if issue_list:
        issues.append((code, "; ".join(issue_list)))

# Summary
print(f"\nPool ETFs: {pool_present}")
print(f"With issues: {len(issues)}")
print(f"Clean: {pool_present - len(issues)}")

record_info.sort(key=lambda x: x[2])
print(f"\n=== FEWEST RECORDS (bottom 15) ===")
for code, name, cnt, start, end, _ in record_info[:15]:
    print(f"  {code} {name}: {cnt} ({start} ~ {end})")

print(f"\n=== ONLY CLOSE-PRICE (no open/high/low) ===")
no_ohlc = [x for x in record_info if not x[5]]
for code, name, cnt, start, end, _ in sorted(no_ohlc, key=lambda x: x[0]):
    print(f"  {code} {name}: {cnt} records ({start} ~ {end})")

print(f"\n=== STALE DATA (last >30 days ago) ===")
stale_list = []
for code, name, cnt, start, end, _ in record_info:
    try:
        days = (today - datetime.date.fromisoformat(end)).days
        if days > 30:
            stale_list.append((code, name, days, end))
    except:
        pass
for code, name, days, end in sorted(stale_list, key=lambda x: -x[2])[:15]:
    print(f"  {code} {name}: {days}d stale ({end})")

print(f"\n=== ALL ISSUES ({len(issues)}) ===")
for code, desc in sorted(issues):
    name = expected.get(code, {}).get("name", "?")
    print(f"  [{code}] {name}: {desc}")

print("\n✓ Done")
