# -*- coding: utf-8 -*-
"""将5只ETF加入主标的池"""
import json
from pathlib import Path

POOL = Path(r"D:\QClaw_Trading\data\etf_pool_V1_full.json")

with open(POOL, encoding="utf-8") as f:
    pool = json.load(f)

existing_codes = {item["code"] for item in pool["data"]}
print(f"池中原有: {len(existing_codes)} 只")

new_entries = [
    {"code": "510050", "name": "上证50ETF", "market": "sh", "type": "宽基ETF"},
    {"code": "159915", "name": "创业板ETF", "market": "sz", "type": "宽基ETF"},
    {"code": "513500", "name": "标普500ETF", "market": "sh", "type": "跨境ETF"},
    {"code": "513100", "name": "纳斯达克ETF", "market": "sh", "type": "跨境ETF"},
    {"code": "515080", "name": "中证红利ETF", "market": "sh", "type": "策略ETF"},
]

added = 0
for entry in new_entries:
    if entry["code"] not in existing_codes:
        pool["data"].append(entry)
        existing_codes.add(entry["code"])
        added += 1
        print(f"  + {entry['code']} {entry['name']} ({entry['type']})")

with open(POOL, "w", encoding="utf-8") as f:
    json.dump(pool, f, ensure_ascii=False, indent=2)

print(f"\n已完成: 新增 {added} 只 → 池中共 {len(pool['data'])} 只")
