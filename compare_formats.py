#!/usr/bin/env python3
import json

codes = ["159902", "510500", "510050", "512880", "159919"]
for code in codes:
    fp = f"D:/QClaw_Trading/data/history/{code}.json"
    raw = json.loads(open(fp, encoding="utf-8").read())
    records = raw if isinstance(raw, list) else raw.get("records", [])
    if not records:
        continue
    r = records[0]
    if isinstance(raw, list):
        print(f"{code} 旧格式: day={r['day']}, volume={r['volume']} (type={type(r['volume']).__name__})")
        print(f"          open={r['open']}, close={r['close']}")
    else:
        print(f"{code} 新格式: date={r['date']}, vol={r['vol']} (type={type(r['vol']).__name__})")
        print(f"          open={r['open']}, close={r['close']}")
