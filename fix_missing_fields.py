#!/usr/bin/env python3
"""
Fix 53 ETFs that have mixed field structure: 
Re-download full OHLCV from Sina for all, replacing old date+close-only data.
"""
import json, sys, time, random, requests
from datetime import datetime
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
pool_map = {e["code"]: e.get("name", "") for e in pool}

# Find ETFs with mixed fields
print("扫描字段不一致的ETF...")
needs_fix = []
for e in pool:
    code = e["code"]
    name = e.get("name", "")
    fp = HISTORY / f"{code}.json"
    if not fp.exists():
        continue
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    if not recs:
        continue
    has_open = sum(1 for r in recs if "open" in r)
    n = len(recs)
    if has_open < n and has_open > 0:
        # Mixed structure: some have OHLCV, some don't
        needs_fix.append((code, name, n, has_open))

print(f"发现 {len(needs_fix)} 只字段不一致")
print(f"全部重下载Sina数据覆盖...\n")

def code_market(code):
    return "sh" if str(code).startswith(("6", "5")) else "sz"

success = 0
for i, (code, name, n, has_open) in enumerate(needs_fix):
    market = code_market(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=1500")
    
    time.sleep(random.uniform(0.3, 0.8))
    
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200 or len(r.text) < 10:
            print(f"  [{i+1}/{len(needs_fix)}] {code} {name[:16]} → ✗ 下载失败")
            continue
        js = r.json()
        if not js:
            print(f"  [{i+1}/{len(needs_fix)}] {code} {name[:16]} → ✗ 空数据")
            continue
        
        records = []
        for row in js:
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
        
        out = {"code": code, "name": name, "records": records}
        (HISTORY / f"{code}.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        
        old_n = n
        new_n = len(records)
        full = sum(1 for r in records if "open" in r)
        print(f"  [{i+1}/{len(needs_fix)}] {code} {name[:16]:<16s} {old_n}→{new_n}条 ✅ 全字段:{full}/{new_n}")
        success += 1
    except Exception as e:
        print(f"  [{i+1}/{len(needs_fix)}] {code} {name[:16]} → ✗ {str(e)[:40]}")

print(f"\n重下载完成: {success}/{len(needs_fix)}")

# Regenerate weekly for these
print(f"\n同步周线...")
wk_updated = 0
for code, name, _, _ in needs_fix:
    hist_fp = HISTORY / f"{code}.json"
    if not hist_fp.exists():
        continue
    raw = json.loads(hist_fp.read_text(encoding="utf-8"))
    recs = raw["records"] if isinstance(raw, dict) else raw
    if not recs:
        continue
    
    # Daily to weekly
    weekly = []
    week_data = []
    for i, r in enumerate(recs):
        dt = datetime.strptime(r["date"], "%Y-%m-%d").date()
        iso_yr, iso_wk, iso_dow = dt.isocalendar()
        week_data.append(r)
        if dt.weekday() == 4 or i == len(recs) - 1:
            close_p = float(r["close"])
            open_p = float(week_data[0].get("open", close_p))
            high_p = float(max(x.get("high", close_p) for x in week_data))
            low_p = float(min(x.get("low", close_p) for x in week_data))
            vol = sum(float(x.get("vol", 0)) for x in week_data)
            rec = {"w": f"{iso_yr}-W{iso_wk:02d}", "date": r["date"], "close": round(close_p, 4)}
            if "open" in week_data[0]:
                rec["open"] = round(open_p, 4)
            if "high" in week_data[0]:
                rec["high"] = round(high_p, 4)
            if "low" in week_data[0]:
                rec["low"] = round(low_p, 4)
            if "vol" in week_data[0] or any("vol" in x for x in week_data):
                rec["vol"] = round(vol, 0)
            weekly.append(rec)
            week_data = []
    
    v2_fp = LONG_V2 / f"{code}.json"
    v2_fp.write_text(
        json.dumps({"code": code, "name": name, "update": weekly[-1]["date"], "records": weekly},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    wk_updated += 1

print(f"周线同步: {wk_updated}个")

# Final check
print(f"\n最终验证...")
still_broken = 0
for code, name, _, _ in needs_fix:
    raw = json.loads((HISTORY / f"{code}.json").read_text(encoding="utf-8"))
    recs = raw["records"]
    full = sum(1 for r in recs if "open" in r)
    total = len(recs)
    if full < total:
        still_broken += 1
        print(f"  ⚠ {code}: {full}/{total} 仍有缺失")

if still_broken == 0:
    print(f"✅ 全部53只修复完成，字段完整率100%")
else:
    print(f"⚠ {still_broken}只仍有问题")
