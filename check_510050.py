import json
from pathlib import Path

fp = Path("D:/QClaw_Trading/data/history/510050.json")
raw = json.loads(fp.read_text(encoding="utf-8"))
recs = raw["records"]
name = raw.get("name", "")
print(f"510050 {name}")
print(f"总记录: {len(recs)}条")
print(f"首条: {recs[0]['date']}")
print(f"末条: {recs[-1]['date']}")
print(f"最新3条:")
for r in recs[-5:]:
    keys = list(r.keys())
    print(f"  {r['date']} o={r.get('open','?')} c={r.get('close','?')} h={r.get('high','?')} l={r.get('low','?')} keys={keys}")

# Check: is it in the pool?
pool = json.loads(Path("D:/QClaw_Trading/data/etf_pool_V1_full.json").read_text(encoding="utf-8"))
in_pool = any(e["code"] == "510050" for e in pool["data"])
print(f"\n在标的池中: {in_pool}")

# If not in pool, which directory does it belong to?
pool_codes = {e["code"] for e in pool["data"]}
all_hist = sorted(Path("D:/QClaw_Trading/data/history").glob("*.json"))
non_pool = [f for f in all_hist if f.stem not in pool_codes and not f.stem.startswith("_")]
print(f"\n非池标文件: {len(non_pool)}个")
for fp2 in non_pool:
    try:
        d = json.loads(fp2.read_text(encoding="utf-8"))
        r = d.get("records", [d] if isinstance(d, list) else [])
        last_date = r[-1]["date"] if r else "?"
        print(f"  {fp2.stem}: 末条={last_date}")
    except:
        pass
