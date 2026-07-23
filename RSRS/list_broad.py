import json, os
d = "D:\\QClaw_Trading\\data\\history"
all_files = [f.replace(".json","") for f in os.listdir(d) if f.endswith(".json")]
zz500 = [c for c in all_files if c.startswith("51") or c.startswith("159")]
for c in sorted(zz500):
    fp = os.path.join(d, c+".json")
    raw = json.load(open(fp,"r",encoding="utf-8"))
    r = raw["records"] if isinstance(raw,dict) else raw
    n = len(r)
    if n > 500:
        print(f"{c}  {n}条  {r[0]['date']} ~ {r[-1]['date']}")
