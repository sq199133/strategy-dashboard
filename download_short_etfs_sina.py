#!/usr/bin/env python3
"""Re-download short-record ETFs using Sina API (push2his blocked, sina works)."""
import json, time, random, re, requests
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

def code_to_market(code):
    """Determine market prefix."""
    c = code.strip()
    if c.startswith("6") or c.startswith("5"):
        return "sh"
    elif c.startswith("1"):
        return "sz"  # LOF
    elif c.startswith("51") or c.startswith("56") or c.startswith("58") or c.startswith("52"):
        return "sh"
    else:
        return "sz"

def download_sina(code):
    """Download daily kline from Sina. Max ~1500 records (~6 years)."""
    market = code_to_market(code)
    url = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500"
    r = requests.get(url, timeout=15)
    if r.status_code != 200 or not r.text.strip() or len(r.text) < 10:
        return None
    try:
        data = json.loads(r.text)
    except:
        return None
    if not data:
        return None
    
    records = []
    for row in data:
        day = row["day"].split()[0]  # "2026-06-08 00:00:00" -> "2026-06-08"
        records.append({
            "date": day,
            "open": float(row["open"]),
            "close": float(row["close"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "vol": int(float(row.get("volume", 0))),
            "amount": int(float(row.get("amount", 0))),
            "chg": 0.0
        })
    records.sort(key=lambda r: r["date"])
    return records

# Short ETFs to fix
short_codes = [
    "560700", "512330", "510180", "513360", "562800", "561380",
    "512040", "517330", "516520", "560120", "515760", "560710",
    "512880", "560160", "513400", "513850",
]

print("=== Re-downloading via Sina API ===")
success = 0
for i, code in enumerate(short_codes):
    name = etf_map.get(code, {}).get("name", "?")
    print(f"  [{i+1}/{len(short_codes)}] {code} {name} ...", end="", flush=True)
    
    time.sleep(0.5 + random.random() * 1)
    records = download_sina(code)
    
    if records and len(records) >= 50:
        out = {"code": code, "name": name, "records": records}
        (HISTORY / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f" ✓ {len(records)} records ({records[0]['date']} ~ {records[-1]['date']})")
        success += 1
    else:
        count = len(records) if records else 0
        print(f" ✗ ({count} records)")

print(f"\nDownloaded: {success}/{len(short_codes)}")

# Final check
print("\n=== Remaining issues ===")
for e in pool["data"]:
    code = e["code"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        print(f"  {code} {e['name']}: MISSING")
        continue
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        records = data.get("records", []) if isinstance(data, dict) else []
        if len(records) < 50:
            print(f"  {code} {e['name']}: only {len(records)} records")
    except:
        print(f"  {code} {e['name']}: parse error")

print("\n=== Verification of fixed 159918 & 510500 ===")
for code in ["159918", "510500"]:
    fp = HISTORY / f"{code}.json"
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data.get("records", [])
    r0 = records[0] if records else {}
    print(f"  {code}: {len(records)} rec, keys={list(r0.keys())[:5]}, date={r0.get('date','?')}")

print("\nDone.")
