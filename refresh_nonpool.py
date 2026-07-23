#!/usr/bin/env python3
"""
Refresh all 117 non-pool files using VIP Sina API (full history).
Only update the existing non-pool files, don't add new ones.
"""
import json, time, random, requests
from datetime import datetime
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
pool_codes = {e["code"] for e in pool}

# Find non-pool files
non_pool = sorted([fp for fp in HISTORY.glob("*.json") 
                   if fp.stem not in pool_codes and not fp.stem.startswith("_")])
print(f"待刷新非池标文件: {len(non_pool)}个\n")

def code_market(code):
    return "sh" if str(code).startswith(("6", "5")) else "sz"

updated = 0
errors = 0
total_added = 0

for i, fp in enumerate(non_pool):
    code = fp.stem
    market = code_market(code)
    time.sleep(random.uniform(0.25, 0.6))
    
    try:
        r = requests.get(
            f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=5000",
            timeout=15)
        if r.status_code != 200:
            errors += 1
            continue
        data = r.json()
        if not data or not isinstance(data, list) or len(data) < 2:
            errors += 1
            continue
        
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
                "amount": 0,
                "chg": 0.0
            })
        records.sort(key=lambda r: r["date"])
        
        # Save
        (HISTORY / f"{code}.json").write_text(
            json.dumps({"code": code, "records": records},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        
        updated += 1
        added = len(records)
        total_added += added
    
        if i % 20 == 0 or i == len(non_pool) - 1:
            print(f"  [{i+1}/{len(non_pool)}] {code} {records[0]['date']}~{records[-1]['date']} = {added}条")
    
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"  [{i+1}/{len(non_pool)}] {code} ✗ {str(e)[:50]}")

print(f"\n✅ {updated}/{len(non_pool)} 刷新完成, {errors} 错误")

# Regenerate weekly for non-pool (if long_v2 dir has them)
print(f"\n同步周线...")
wk_updated = 0
for code in [fp.stem for fp in non_pool]:
    src = HISTORY / f"{code}.json"
    if not src.exists():
        continue
    raw = json.loads(src.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if not recs:
        continue
    
    weekly = []
    week_data = []
    for j, r in enumerate(recs):
        dt_obj = datetime.strptime(r["date"], "%Y-%m-%d").date()
        week_data.append(r)
        if dt_obj.weekday() == 4 or j == len(recs) - 1:
            close_p = float(r["close"])
            open_p = float(week_data[0].get("open", close_p))
            high_p = float(max(x.get("high", close_p) for x in week_data))
            low_p = float(min(x.get("low", close_p) for x in week_data))
            vol = sum(float(x.get("vol", 0)) for x in week_data)
            rec_w = {"w": f"{dt_obj.isocalendar()[0]}-W{dt_obj.isocalendar()[1]:02d}",
                     "date": r["date"], "close": round(close_p, 4)}
            if "open" in week_data[0]:
                rec_w["open"] = round(open_p, 4)
            if "high" in week_data[0]:
                rec_w["high"] = round(high_p, 4)
            if "low" in week_data[0]:
                rec_w["low"] = round(low_p, 4)
            if "vol" in week_data[0] or any("vol" in x for x in week_data):
                rec_w["vol"] = round(vol, 0)
            weekly.append(rec_w)
            week_data = []
    
    if weekly:
        v2_fp = LONG_V2 / f"{code}.json"
        v2_fp.write_text(
            json.dumps({"code": code, "records": weekly, "update": recs[-1]["date"]},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        wk_updated += 1

print(f"周线: {wk_updated}/{len(non_pool)}个")

# Summary
print(f"\n=== 最终日期分布(非池标) ===")
from collections import Counter
dates = []
for fp in non_pool:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if recs:
        dates.append(recs[-1]["date"])
for d, cnt in sorted(Counter(dates).items(), reverse=True):
    m = " ✅" if d == max(dates) else ""
    print(f"  {d}: {cnt}只{m}")

total = sum(len(json.loads(fp.read_text(encoding="utf-8")).get("records", [])) for fp in non_pool)
pool_total = sum(
    len(json.loads((HISTORY / f"{e['code']}.json").read_text(encoding="utf-8")).get("records", []))
    for e in pool)
print(f"\n池标: {pool_total}条  非池标: {total}条  总计: {pool_total + total}条")
