#!/usr/bin/env python3
"""Check file structure for field-missing ETFs."""
import json
from pathlib import Path

codes = ["512400", "159949", "510170", "159792", "562060", "562010"]
for code in codes:
    fp = Path(f"D:/QClaw_Trading/data/history/{code}.json")
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw["records"]
    name = raw.get("name", "")
    print(f"=== {code} {name} ({len(recs)}条) ===")
    
    # First 5 records
    for i, r in enumerate(recs[:5]):
        print(f"  [{i}] keys={list(r.keys())} date={r['date']} c={r.get('close','?')} o={r.get('open','?')} h={r.get('high','?')}")
    
    # Check transition point - find where full fields end
    full_count = sum(1 for r in recs if "open" in r)
    print(f"  有完整字段(含open/high/low): {full_count}条")
    print(f"  仅date+close: {len(recs) - full_count}条")
    
    # Show last 3 records
    for i in range(-3, 0):
        idx = len(recs) + i
        r = recs[idx]
        print(f"  [{idx}] keys={list(r.keys())} date={r['date']} c={r.get('close','?')}")
    print()
