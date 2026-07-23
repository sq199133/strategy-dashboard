#!/usr/bin/env python3
"""
Daily batch update for all 195 pool ETFs.
Download latest data from Sina, merge, then sync weekly.
"""
import json, time, random, requests
from datetime import datetime, date
from pathlib import Path

HISTORY = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
print(f"批量更新 {len(pool)} 只ETF...\n")

today_str = date.today().isoformat()
print(f"目标日期: {today_str}")

def code_market(code):
    return "sh" if str(code).startswith(("6", "5")) else "sz"

# Phase 1: download latest 50 records from Sina and merge
updated = 0
added_total = 0
errors = 0

for i, e in enumerate(pool):
    code = e["code"]
    name = e.get("name", "")
    market = code_market(code)
    short_name = name[:16]
    
    # Use VIP API for all (reliable, consistent format)
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={market}{code}&scale=240&datalen=50")
    
    time.sleep(random.uniform(0.2, 0.5))
    
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            errors += 1
            continue
        data = r.json()
        if not data or not isinstance(data, list):
            errors += 1
            continue
        
        new_recs = []
        for row in data:
            day = row["day"].split()[0]
            new_recs.append({
                "date": day,
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "vol": int(float(row.get("volume", 0))),
                "amount": 0,
                "chg": 0.0
            })
        new_recs.sort(key=lambda r: r["date"])
        
        # Merge with existing
        fp = HISTORY / f"{code}.json"
        old_raw = {}
        old_recs = []
        if fp.exists():
            old_raw = json.loads(fp.read_text(encoding="utf-8"))
            old_recs = old_raw.get("records", [])
        
        # Deduplicate by date, keep new records
        seen_dates = set()
        merged = []
        for r in new_recs:
            seen_dates.add(r["date"])
            merged.append(r)
        for r in old_recs:
            if r["date"] not in seen_dates:
                merged.append(r)
        merged.sort(key=lambda r: r["date"])
        
        added = len(merged) - len(old_recs)
        if added > 0:
            updated += 1
            added_total += added
            
            # Save
            (HISTORY / f"{code}.json").write_text(
                json.dumps({"code": code, "name": name, "records": merged},
                           ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8")
            
            if i % 20 == 0 or i == len(pool) - 1:
                print(f"  [{i+1}/{len(pool)}] {code} {short_name:<16s} +{added}条 → {len(merged)}条")
        else:
            if i % 20 == 0 or i == len(pool) - 1:
                print(f"  [{i+1}/{len(pool)}] {code} {short_name:<16s} 无新增")
                
    except Exception as ex:
        errors += 1
        if errors <= 3:
            print(f"  [{i+1}/{len(pool)}] {code} {short_name:<16s} ✗ {str(ex)[:40]}")

print(f"\n✅ 更新完成: {updated}/{len(pool)} 有新增 (+{added_total}条), {errors} 错误")

# Phase 2: sync weekly
if added_total > 0:
    print(f"\n同步周线...")
    wk_updated = 0
    
    for e in pool:
        code = e["code"]
        name = e.get("name", "")
        fp = HISTORY / f"{code}.json"
        if not fp.exists():
            continue
        
        raw = json.loads(fp.read_text(encoding="utf-8"))
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
        
        v2_fp = LONG_V2 / f"{code}.json"
        v2_fp.write_text(
            json.dumps({"code": code, "name": name, "update": recs[-1]["date"], "records": weekly},
                       ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        wk_updated += 1
    
    print(f"周线同步: {wk_updated}个")

print(f"\n最终检查:")
# Check the latest date across all files
latest_dates = {}
for fp in sorted(HISTORY.glob("*.json")):
    if fp.stem.startswith("_"):
        continue
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if recs:
        latest_dates[fp.stem] = recs[-1]["date"]

# Count by date
from collections import Counter
date_counts = Counter(latest_dates.values())
print(f"最新日期分布:")
for d in sorted(date_counts.keys(), reverse=True):
    more = " ✅" if d == max(date_counts.keys()) else ""
    print(f"  {d}: {date_counts[d]}只{more}")

total = sum(len(json.loads((HISTORY / f"{e['code']}.json").read_text(encoding="utf-8")).get("records", []))
           for e in pool if (HISTORY / f"{e['code']}.json").exists())
print(f"总记录数: {total}")
