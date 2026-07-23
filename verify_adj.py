import json
from pathlib import Path
from collections import Counter

# Check 159901 which had 3 events over 11 years
fp = Path("D:/QClaw_Trading/data/history/159901.json")
raw = json.loads(fp.read_text(encoding="utf-8"))
recs = raw["records"]
adj = raw.get("adjustments", [])
print(f"159901 (深100ETF): {len(recs)}条")
print(f"  修复: {len(adj)}个事件")
for a in adj:
    print(f"    {a['date']} f={a['factor']}")
print(f"  首条: {recs[0]['date']} C:{recs[0]['close']}")
print(f"  末条: {recs[-1]['date']} C:{recs[-1]['close']}")
dates = [r["date"] for r in recs]
first_evt_idx = dates.index(adj[0]["date"])
print(f"  2010年前复权验证(事件1前):")
for i in range(max(0,first_evt_idx-3), first_evt_idx):
    r = recs[i]
    chg = ""
    if i > 0:
        pc = float(recs[i-1]["close"])
        cc = float(r["close"])
        if pc > 0:
            chg = f"{(cc-pc)/pc*100:.2f}%"
    print(f"    {r['date']} C:{r['close']:.4f} {chg}")

print()

# Overall coverage
all_files = sorted(Path("D:/QClaw_Trading/data/history").glob("*.json"))
all_files = [f for f in all_files if not f.stem.startswith("_")]
min_year, max_year = 3000, 0
for fp in all_files:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    recs = raw.get("records", [])
    if recs:
        y_first = int(recs[0]["date"][:4])
        y_last = int(recs[-1]["date"][:4])
        if y_first < min_year: min_year = y_first
        if y_last > max_year: max_year = y_last

print(f"覆盖年份: {min_year} ~ {max_year}")
print(f"文件数: {len(all_files)}")

# Adjustments per year
yr_counts = Counter()
for fp in all_files:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    for a in raw.get("adjustments", []):
        yr_counts[a["date"][:4]] += 1
print(f"修复事件年份分布:")
for yr in sorted(yr_counts):
    print(f"  {yr}: {yr_counts[yr]}次")
