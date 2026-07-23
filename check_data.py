#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick check: latest week for etf data files."""
import json, os, glob
from datetime import datetime as dt

HISTORY_DIR = r"D:\Qclaw_Trading\data\history_long_v2"
files = glob.glob(os.path.join(HISTORY_DIR, "*.json"))
weeks = {}
for f in files:
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        recs = d.get("records", []) if isinstance(d, dict) else d
        if recs:
            ds = recs[-1].get("date", "") or recs[-1].get("w", "")
            if ds:
                y, wn, _ = dt.strptime(ds, "%Y-%m-%d").isocalendar()
                wk = "{}-W{:02d}".format(y, wn)
                weeks[wk] = weeks.get(wk, 0) + 1
    except:
        pass
srt = sorted(weeks.items(), key=lambda x: x[0], reverse=True)
print("Latest weeks with ETF data:")
for wk, cnt in srt[:10]:
    print("  {}: {} ETFs".format(wk, cnt))
