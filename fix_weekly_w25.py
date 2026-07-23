"""Fix W25 gap issue: close week when trading gap >= 2 calendar days.
Also regenerate all weekly files for all 195 ETFs.
"""
import json, datetime
from pathlib import Path

HIST = Path("D:/QClaw_Trading/data/history")
LONG_V2 = Path("D:/QClaw_Trading/data/history_long_v2")
POOL = Path("D:/QClaw_Trading/data/etf_pool_V1_full.json")

pool = json.loads(POOL.read_text(encoding="utf-8"))["data"]
etf_map = {e["code"]: e for e in pool}

def read_json_safe(fp):
    raw = fp.read_bytes()
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            return json.loads(raw.decode(enc))
        except:
            continue
    return None

def write_json_safe(fp, data):
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    fp.write_text(text, encoding="utf-8")

def daily_to_weekly(daily_records):
    """Aggregate daily → weekly.
    
    Week closes on:
    1. Friday (weekday == 4) - normal trading week end
    2. Trading gap >= 2 calendar days (holiday/weekend break)
       E.g. Thu 6/18 → Mon 6/22 = gap 3 days → close on Thu 6/18
    3. Last record always closes
    """
    if not daily_records:
        return []
    
    weekly = []
    week_data = []
    prev_dt = None
    
    for i, r in enumerate(daily_records):
        dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
        
        # Check: did we just cross a holiday/weekend gap?
        # If prev_dt exists and gap >= 2 calendar days, close current week
        # BEFORE adding the new record (close with the record BEFORE the gap)
        if prev_dt is not None:
            gap = (dt - prev_dt).days
            if gap >= 2 and week_data:
                _close_week(week_data, weekly, daily_records[i-1])
                week_data = []
        
        week_data.append(r)
        prev_dt = dt
        
        # Normal Friday close
        if dt.weekday() == 4:
            _close_week(week_data, weekly, r)
            week_data = []
        
        # Last record
        elif i == len(daily_records) - 1 and week_data:
            _close_week(week_data, weekly, r)
            week_data = []
    
    return weekly

def _close_week(week_data, weekly, anchor_record):
    """Aggregate week_data into one weekly bar, append to weekly list."""
    iso_yr, iso_wk, _ = anchor_record["date"].split("-")
    iso_yr = int(iso_yr)
    iso_wk = int(iso_wk)
    close_p = float(anchor_record["close"])
    open_p = float(week_data[0].get("open", close_p))
    high_p = float(max(x.get("high", close_p) for x in week_data))
    low_p = float(min(x.get("low", close_p) for x in week_data))
    vol = sum(float(x.get("vol", 0)) for x in week_data)
    
    rec = {
        "w": f"{iso_yr}-W{iso_wk:02d}",
        "date": anchor_record["date"],
        "close": round(close_p, 4),
    }
    if "open" in week_data[0]:
        rec["open"] = round(open_p, 4)
    if "high" in week_data[0]:
        rec["high"] = round(high_p, 4)
    if "low" in week_data[0]:
        rec["low"] = round(low_p, 4)
    if "vol" in week_data[0] or any("vol" in x for x in week_data):
        rec["vol"] = round(vol, 0)
    
    weekly.append(rec)

# === Regenerate all 195 weekly files ===
print("Regenerating weekly files for all 195 ETFs...")
updated = 0
skipped = 0

for item in pool:
    code = item["code"]
    hist_fp = HIST / f"{code}.json"
    v2_fp = LONG_V2 / f"{code}.json"
    
    hist = read_json_safe(hist_fp)
    if not hist:
        print(f"  {code}: HIST MISSING")
        continue
    
    recs = hist.get("records", hist) if isinstance(hist, dict) else hist
    if not recs:
        skipped += 1
        continue
    
    weekly = daily_to_weekly(recs)
    
    name = etf_map.get(code, {}).get("name", "")
    data = {
        "code": code,
        "name": name,
        "update": weekly[-1]["date"] if weekly else "",
        "records": weekly
    }
    write_json_safe(v2_fp, data)
    
    # Check if W25 exists
    w25_exists = any(w["w"] == "2026-W25" for w in weekly)
    marker = " ✓ W25" if w25_exists else "   NO W25"
    print(f"  {code}{marker}")
    updated += 1

print(f"\nDone: {updated} updated, {skipped} skipped")
