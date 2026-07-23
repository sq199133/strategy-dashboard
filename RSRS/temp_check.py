import json
raw = json.load(open("D:\\QClaw_Trading\\data\\history\\510300.json", "r", encoding="utf-8"))
recs = raw["records"]
print(f'First: {recs[0]["date"]}  Last: {recs[-1]["date"]}  Count: {len(recs)}')
