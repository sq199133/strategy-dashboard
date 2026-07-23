#!/usr/bin/env python3
import json, time, random
from pathlib import Path

HISTORY_DIR = Path("D:/QClaw_Trading/data/history")

# Fix date sort errors
for code in ["159918", "510500"]:
    fp = HISTORY_DIR / f"{code}.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("records", [])
    
    print(f"{code}: {len(records)} records, type=list={isinstance(data, list)}")
    if records:
        r = records[0]
        print(f"  First record keys: {list(r.keys())}")
        print(f"  Date value: {r.get('date','?')} (type={type(r.get('date','?')).__name__})")
        # Check date types
        types = set(type(r.get('date')).__name__ for r in records)
        print(f"  Date types: {types}")
        
        # Fix date values that might be floats/ints
        fixed = 0
        for r in records:
            d = r.get("date")
            if isinstance(d, (int, float)):
                d_str = str(int(d))
                if len(d_str) == 8 and d_str.isdigit():
                    r["date"] = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
                    fixed += 1
        
        if fixed:
            print(f"  Fixed {fixed} numeric dates")
        
        # Now sort
        records.sort(key=lambda r: str(r.get("date", "")))
        
        # Write back as dict format
        out = {"code": code, "name": data.get("name", "?"), "records": records}
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        print(f"  ✓ Saved {len(records)} records")

# Try downloading short ETFs with delays
import akshare as ak

short_codes = [
    "560700", "512330", "510180", "513360", "562800", "561380",
    "512040", "517330", "516520", "560120", "515760", "560710",
    "512880", "560160", "513400", "513850",
]

pool = json.loads(Path("D:/QClaw_Trading/data/etf_pool_V1_full.json").read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

print("\n=== Retrying downloads with delays ===")
success = 0
for i, code in enumerate(short_codes):
    name = etf_map.get(code, {}).get("name", "?")
    print(f"\n[{i+1}/{len(short_codes)}] {code} {name}...")
    
    for attempt in range(3):
        try:
            time.sleep(2 + random.random() * 3)  # 2-5s delay
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
                print(f"  ✓ {len(records)} records")
                success += 1
                break
            else:
                print(f"  ✗ attempt {attempt+1}: 0 records")
        except Exception as e:
            err = str(e)[:80]
            print(f"  ✗ attempt {attempt+1}: {err}")
            time.sleep(3)

print(f"\nDownloaded: {success}/{len(short_codes)}")

# Final short list
print("\n=== Remaining short (<50 records) ===")
for fp in sorted(HISTORY_DIR.glob("*.json")):
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        records = data.get("records", []) if isinstance(data, dict) else data
        if len(records) < 50:
            print(f"  {fp.stem}: {len(records)}")
    except:
        pass
