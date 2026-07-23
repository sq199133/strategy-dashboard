"""Verify W25 data in weekly file"""
import json
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history_long_v2/159928.json")
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d = json.loads(fp.read_bytes().decode(enc)); break
    except:
        pass
recs = d.get("records", d) if isinstance(d, dict) else d

print("W24/W25/W26 records:")
for r in recs:
    w = r.get("w", "")
    if any(x in w for x in ["W24", "W25", "W26"]):
        date = r.get("date", "")
        close = r.get("close", "")
        print(f"  {w} date={date} close={close}")

print(f"\nTotal: {len(recs)} weekly records")

# Also check W22 (端午那周 in daily - should have端午data)
print("\n=== Daily W22 (端午那周 5/30-6/2) ===")
fp2 = Path("D:/QClaw_Trading/data/history/159928.json")
for enc in ["utf-8", "gbk", "gb18030"]:
    try:
        d2 = json.loads(fp2.read_bytes().decode(enc)); break
    except:
        pass
recs2 = d2.get("records", d2) if isinstance(d2, dict) else d2
w22_dates = ["2026-05-30", "2026-05-31", "2026-06-01", "2026-06-02"]
w22 = [r for r in recs2 if isinstance(r, dict) and r.get("date", "") in w22_dates]
print(f"Records in W22 (端午): {len(w22)}")
for r in w22:
    print(f"  {r['date']} close={r['close']}")
