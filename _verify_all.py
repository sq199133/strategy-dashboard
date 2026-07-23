# -*- coding: utf-8 -*-
import json
from pathlib import Path

HIST = Path(r"D:\QClaw_Trading\data\history")
WEEKLY = Path(r"D:\QClaw_Trading\data\history_long_v2")
with open(HIST.parent / "etf_pool_V1_full.json", encoding="utf-8") as f:
    codes = [x["code"] for x in json.load(f)["data"]]
codes += ["512890","515910","512750","159399"]
codes = list(set(codes))

d_ok = d_stale = 0
for c in codes:
    hf = HIST / f"{c}.json"
    if not hf.exists(): continue
    with open(hf, encoding="utf-8") as f:
        recs = json.load(f).get("records",[])
    last = recs[-1]["date"] if recs else ""
    if last == "2026-07-17": d_ok += 1
    else: d_stale += 1
print(f"日线: OK={d_ok} STALE={d_stale}")

wf = WEEKLY / "510500.json"
with open(wf, encoding="utf-8") as f:
    last_w = json.load(f)["records"][-1]["date"]
print(f"周线510500: last={last_w}")

hf = HIST / "000300.json"
with open(hf, encoding="utf-8") as f:
    last300 = json.load(f)["records"][-1]["date"]
print(f"000300: last={last300}")
