"""Check the ACTUAL weekly file for 159928"""
import json
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history_long_v2/159928.json")
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d = json.loads(fp.read_bytes().decode(enc)); break
    except: pass
recs = d.get("records", d) if isinstance(d, dict) else d

# Find W24, W25, W26
for r in recs:
    w = r.get("w","")
    if any(x in w for x in ["W24","W25","W26"]):
        print(f"  {w} date={r['date']} close={r.get('close')}")

# Also count
w_counts = {}
for r in recs:
    w = r.get("w","")
    w_counts[w] = w_counts.get(w,0) + 1

# Find 2026 weeks
print(f"\n2026 weeks:")
for w, c in sorted(w_counts.items()):
    if "2026" in w:
        print(f"  {w}: {c}")
