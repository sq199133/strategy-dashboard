# -*- coding: utf-8 -*-
import json
from pathlib import Path

HIST = Path(r"D:\QClaw_Trading\data\history")
POOL_FILE = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")

with open(POOL_FILE, encoding="utf-8") as f:
    obj = json.load(f)
codes = [item["code"] for item in obj["data"]]
for fc in ["512890", "515910", "512750", "159399"]:
    if fc not in codes:
        codes.append(fc)

today = "2026-07-14"
ok = stale = 0
stale_list = []
for c in codes:
    hf = HIST / f"{c}.json"
    if not hf.exists():
        stale_list.append(f"{c}: NOFILE")
        stale += 1
        continue
    try:
        with open(hf, encoding="utf-8") as f:
            obj2 = json.load(f)
        recs = obj2.get("records", [])
        last = recs[-1]["date"] if recs else None
        if last == today:
            ok += 1
        else:
            stale_list.append(f"{c}: last={last}")
            stale += 1
    except Exception as e:
        stale_list.append(f"{c}: ERR {e}")
        stale += 1

print(f"ETF: OK={ok}  STALE={stale}  (total={len(codes)})")

# 000300
hf = HIST / "000300.json"
with open(hf, encoding="utf-8") as f:
    obj2 = json.load(f)
last300 = obj2["records"][-1]["date"]
print(f"000300: last={last300}")

# Weekly
WEEKLY = Path(r"D:\QClaw_Trading\data\history_long_v2")
wf = WEEKLY / "510500.json"
with open(wf, encoding="utf-8") as f:
    obj3 = json.load(f)
last_w = obj3["records"][-1]["date"]
print(f"周线: last={last_w} (本周五7/18聚合)")

if stale_list:
    print("\nStale:")
    for s in stale_list[:10]:
        print(f"  {s}")
