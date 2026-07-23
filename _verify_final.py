# -*- coding: utf-8 -*-
import json
from pathlib import Path

hist = Path(r"D:\QClaw_Trading\data\history")
for c in ["510050", "159915", "513500", "513100", "515080"]:
    f = hist / f"{c}.json"
    recs = json.loads(f.read_text(encoding="utf8"))["records"]
    print(f"{c}: {recs[-1]['date']} C={recs[-1]['close']}")
