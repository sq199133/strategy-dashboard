# -*- coding: utf-8 -*-
import json
from pathlib import Path

pool = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")
codes = [x["code"] for x in json.loads(pool.read_text(encoding="utf8"))["data"]]
print(f"池中标的: {len(codes)} 只")
for c in ["510050", "159915", "513500", "513100", "515080"]:
    print(f"  {c}: {'OK' if c in codes else 'MISS'}")
