"""Debug: trace gap detection around 6/18"""
import json, datetime
from pathlib import Path

HIST = Path("D:/QClaw_Trading/data/history")

fp = HIST / "159928.json"
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d = json.loads(fp.read_bytes().decode(enc)); break
    except: pass
recs = d.get("records", d) if isinstance(d, dict) else d

# Find records around 6/15-6/22
print("Daily records around端午假期:")
for r in recs:
    if isinstance(r, dict) and "date" in r:
        dt_str = r["date"]
        if "2026-06-15" <= dt_str <= "2026-06-23":
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
            iso = dt.isocalendar()
            print(f"  {dt_str} weekday={dt.weekday()} iso_w={iso[1]}")

print()
print("=== Simulating gap detection ===")
week_data = []
weekly = []
prev_dt = None

for i, r in enumerate(recs):
    dt_str = r["date"]
    if not (isinstance(r, dict) and "date" in r):
        continue
    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
    
    if prev_dt is not None:
        gap = (dt - prev_dt).days
        if gap >= 2:
            print(f"  GAP at {dt_str}: {gap} days, prev={prev_dt}")
    
    prev_dt = dt

print()
print("=== Checking weekly output ===")
fp2 = Path("D:/QClaw_Trading/data/history_long_v2/159928.json")
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d2 = json.loads(fp2.read_bytes().decode(enc)); break
    except: pass
recs2 = d2.get("records", d2) if isinstance(d2, dict) else d2
print(f"Total weekly records: {len(recs2)}")
for w in recs2:
    if "2026-W24" in w.get("w","") or "2026-W25" in w.get("w","") or "2026-W26" in w.get("w",""):
        print(f"  {w['w']} date={w['date']} close={w['close']}")
