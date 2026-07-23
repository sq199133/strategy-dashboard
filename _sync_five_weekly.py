# -*- coding: utf-8 -*-
import json
from pathlib import Path
from datetime import datetime

HIST = Path(r"D:\QClaw_Trading\data\history")
WEEKLY = Path(r"D:\QClaw_Trading\data\history_long_v2")

def daily_to_weekly(records):
    weekly = {}
    for r in records:
        dt = datetime.strptime(r["date"], "%Y-%m-%d")
        wk = dt.strftime("%Y-%W")
        vol_key = "vol" if "vol" in r else "volume"
        if wk not in weekly:
            weekly[wk] = {"date": r["date"], "open": r["open"],
                "high": r["high"], "low": r["low"], "close": r["close"],
                vol_key: r.get(vol_key, 0)}
        else:
            w = weekly[wk]
            w["high"] = max(w["high"], r["high"])
            w["low"] = min(w["low"], r["low"])
            w["close"] = r["close"]
            w[vol_key] = w.get(vol_key, 0) + r.get(vol_key, 0)
            w["date"] = r["date"]
    return sorted(weekly.values(), key=lambda x: x["date"])

codes = ["510050","159915","513500","513100","515080"]
for c in codes:
    hf = HIST / f"{c}.json"
    wf = WEEKLY / f"{c}.json"
    with open(hf, encoding="utf-8") as f:
        drecs = json.load(f).get("records", [])
    weekly = daily_to_weekly(drecs)
    obj = {"records": weekly, "update": weekly[-1]["date"] if weekly else ""}
    with open(wf, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"  {c}: 周线 {len(weekly)} 条, last={weekly[-1]['date']}")
