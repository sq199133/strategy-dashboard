# -*- coding: utf-8 -*-
import json
from pathlib import Path

HIST = Path(r"D:\QClaw_Trading\data\history")
codes = ["510050", "159915", "513500", "513100", "515080"]

print("标的\t\t代码\t最后日期")
print("-" * 50)
for c in codes:
    hf = HIST / f"{c}.json"
    if hf.exists():
        with open(hf, encoding="utf-8") as f:
            recs = json.load(f).get("records", [])
        last = recs[-1]["date"] if recs else "N/A"
        names = {"510050":"上证50ETF","159915":"创业板ETF","513500":"标普500ETF","513100":"纳斯达克ETF","515080":"中证红利ETF"}
        print(f"{names[c]}\t{c}\t{last}")
    else:
        print(f"{c}\t--\t❌ 不存在")

# 检查周线
W = Path(r"D:\QClaw_Trading\data\history_long_v2")
for c in codes:
    wf = W / f"{c}.json"
    if wf.exists():
        with open(wf, encoding="utf-8") as f:
            recs = json.load(f).get("records", [])
        last_w = recs[-1]["date"] if recs else "N/A"
        print(f"  周线 {c}: {last_w}")
