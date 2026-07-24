import json
from pathlib import Path
H = Path("D:/QClaw_Trading/data/history")
cnt = {}
for f in sorted(H.glob("*.json")):
    if f.stem.startswith("_"): continue
    r = json.loads(f.read_text(encoding="utf-8")).get("records",[])
    if r:
        dt = r[-1]["date"]
        cnt[dt] = cnt.get(dt,0) + 1
print("日线最新日期分布:")
for dt in sorted(cnt.keys()):
    print(f"  {dt}: {cnt[dt]}只")
print()
# 找漏掉的
for f in sorted(H.glob("*.json")):
    if f.stem.startswith("_"): continue
    r = json.loads(f.read_text(encoding="utf-8")).get("records",[])
    if r and r[-1]["date"] < "2026-07-24":
        print(f"  漏: {f.stem} -> {r[-1]['date']}")
