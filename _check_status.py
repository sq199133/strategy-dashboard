# -*- coding: utf-8 -*-
import json
from pathlib import Path

HIST = Path(r"D:\QClaw_Trading\data\history")
POOL = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")
with open(POOL, encoding="utf-8") as f:
    codes = [x["code"] for x in json.load(f)["data"]]
codes += ["512890", "515910", "512750", "159399"]
codes = list(set(codes))

dates = {}
for c in codes:
    hf = HIST / f"{c}.json"
    if not hf.exists():
        continue
    try:
        with open(hf, encoding="utf-8") as f:
            recs = json.load(f).get("records", [])
        last = recs[-1]["date"] if recs else None
        dates[last] = dates.get(last, 0) + 1
    except:
        pass

print("日线分布:")
for d in sorted(dates.keys(), reverse=True)[:5]:
    print(f"  {d}: {dates[d]}只")

# 000300
hf = HIST / "000300.json"
with open(hf, encoding="utf-8") as f:
    print(f"000300: last={json.load(f)['records'][-1]['date']}")

# 周线
WEEKLY = Path(r"D:\QClaw_Trading\data\history_long_v2")
wf = WEEKLY / "510500.json"
with open(wf, encoding="utf-8") as f:
    print(f"周线510500: last={json.load(f)['records'][-1]['date']}")
