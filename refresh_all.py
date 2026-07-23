"""Force update all 195 pool ETFs to latest using DataFetcher.
Appends any missing recent days to local JSON files.
"""
import json, time, random
from pathlib import Path
from qclaw_stock_data import DataFetcher

POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")
HIST = Path("D:/QClaw_Trading/data/history")

f = DataFetcher()
pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
print(f"Pool: {len(pool)} ETFs, refreshing to latest...")

updated = 0
errors = 0
skipped = 0

for i, item in enumerate(pool):
    code = item["code"]
    fp = HIST / f"{code}.json"
    
    # Load current local data
    raw = fp.read_bytes()
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            local = json.loads(raw.decode(enc))
            break
        except:
            local = None
            break
    
    if not local:
        print(f"  [{i+1}/{len(pool)}] {code}: bad file, skip")
        errors += 1
        continue
    
    recs = local.get("records", local) if isinstance(local, dict) else local
    local_dates = set()
    for r in recs:
        if isinstance(r, dict) and "date" in r:
            local_dates.add(r["date"])
    
    # Fetch latest 10 days from API
    api_data = f.kline(code, 10)
    if not api_data:
        print(f"  [{i+1}/{len(pool)}] {code}: API no data")
        errors += 1
        continue
    
    # Find new dates
    new_dates = [row for row in api_data if row["date"] not in local_dates]
    
    if not new_dates:
        # Already up to date - verify last date
        last_local = max(local_dates) if local_dates else "N/A"
        last_api = max(r["date"] for r in api_data) if api_data else "N/A"
        if (i+1) % 50 == 0:
            print(f"  [{i+1}/{len(pool)}] {code}: up-to-date ({last_local})")
    else:
        # Append new records, keep sorted
        rec_map = {r["date"]: r for r in recs if isinstance(r, dict) and "date" in r}
        for row in new_dates:
            rec_map[row["date"]] = row
        new_recs = sorted(rec_map.values(), key=lambda x: x["date"])
        
        # Save back
        if isinstance(local, dict):
            local["records"] = new_recs
            fp.write_text(json.dumps(local, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        else:
            fp.write_text(json.dumps(new_recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        
        print(f"  [{i+1}/{len(pool)}] {code}: +{len(new_dates)} new ({new_dates[0]['date']}..{new_dates[-1]['date']})")
        updated += 1
    
    time.sleep(random.uniform(0.3, 0.8))
    
    if (i+1) % 50 == 0:
        print(f"\n  --- Progress: {i+1}/{len(pool)} ---\n")

print(f"\n=== Done ===")
print(f"  Updated: {updated}")
print(f"  Errors:  {errors}")
print(f"  Skip:    {skipped}")
