import json, sys
from pathlib import Path
H = Path("D:/QClaw_Trading/data/history")
for f in sorted(H.glob("*.json")):
    if f.stem.startswith("_"): continue
    r = json.loads(f.read_text(encoding="utf-8")).get("records",[])
    if r and r[-1]["date"] < "2026-07-23":
        print(f"{f.stem}: last={r[-1]['date']}")
        break
else:
    print("ok all 7/23")
