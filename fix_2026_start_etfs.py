#!/usr/bin/env python3
"""Re-download 20 old ETFs that only have data from 2026-01-05."""
import json, time, random, requests
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))
etf_map = {e["code"]: e for e in pool["data"]}

# ETFs that START at 2026-01-05 — these are OLD ETFs, need full history
old_etfs_2026 = [
    "562910", "515860", "588000", "562500", "510880", "512170",
    "513290", "513090", "517520", "512660", "515790", "588220",
    "513690", "560280", "515210", "560080", "517380", "588230",
    "588020", "512580", "562570", "515580", "562850",
    # Also fix these that have broken dates
    "159918", "510500",
]

def code_market(code):
    c = str(code).strip()
    if c.startswith(("6", "5")):
        return "sh"
    return "sz"

def download_sina(code):
    market = code_market(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or not r.text.strip() or len(r.text) < 10:
            return None
        data = r.json()
        if not data:
            return None
        records = []
        for row in data:
            day = row["day"].split()[0]
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
    except Exception:
        return None

print(f"需要补充 {len(old_etfs_2026)} 只ETF的历史数据...")
success = 0
for i, code in enumerate(old_etfs_2026):
    name = etf_map.get(code, {}).get("name", "?")
    print(f"  [{i+1}/{len(old_etfs_2026)}] {code} {name} ...", end="", flush=True)
    
    time.sleep(0.5 + random.random() * 1)
    records = download_sina(code)
    
    if records and len(records) >= 100:
        out = {"code": code, "name": name, "records": records}
        (HISTORY / f"{code}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f" ✓ {len(records)}条 ({records[0]['date']} ~ {records[-1]['date']})")
        success += 1
    else:
        n = len(records) if records else 0
        print(f" ✗ ({n}条)")

print(f"\n完成: {success}/{len(old_etfs_2026)}")

# Final count
print("\n=== 更新后2026年开始的ETF ===")
from collections import Counter
years = Counter()
for e in pool["data"]:
    code = e["code"]
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        continue
    data = json.loads(fp.read_text(encoding="utf-8"))
    records = data.get("records", [])
    if not records:
        continue
    year = records[0]["date"][:4]
    years[year] += 1
    if year == "2026":
        print(f"  {code} {e['name']}: {records[0]['date']} ~ ({len(records)}条)")

print(f"\n开始年份分布:")
for y in sorted(years):
    print(f"  {y}: {years[y]}只")
