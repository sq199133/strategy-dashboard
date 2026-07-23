"""Debug _close_week week number for 6/18"""
import datetime

# Check ISO week for various dates
for dt_str in ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-22", "2026-06-26"]:
    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
    iso = dt.isocalendar()
    yr, wk, dow = iso
    print(f"{dt_str}: iso_yr={yr} iso_wk={wk} dow={dow} => w='{yr}-W{wk:02d}'")

print()
# Simulate daily_to_weekly on just the relevant portion
import json
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history/159928.json")
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d = json.loads(fp.read_bytes().decode(enc)); break
    except: pass
recs = d.get("records", d) if isinstance(d, dict) else d

# Find 6/15 onward
recent = [r for r in recs if isinstance(r, dict) and "date" in r and r["date"] >= "2026-06-12"]
print(f"Recent records (from 6/12):")
for r in recent[:20]:
    dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
    iso = dt.isocalendar()
    print(f"  {r['date']} weekday={dt.weekday()} iso_w={iso[1]} => '{iso[0]}-W{iso[1]:02d}'")

# Manually trace the gap detection
print()
print("Manual trace:")
prev_dt = None
for i, r in enumerate(recent):
    dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
    if prev_dt is not None:
        gap = (dt - prev_dt).days
        if gap >= 2:
            iso = prev_dt.isocalendar()
            print(f"  GAP at {r['date']}: {gap} days -> close week at {prev_dt} => w='{iso[0]}-W{iso[1]:02d}'")
    prev_dt = dt
