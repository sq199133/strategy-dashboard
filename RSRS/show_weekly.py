import json
d = json.load(open("D:\\QClaw_Trading\\RSRS\\weekly_2026_results.json", "r", encoding="utf-8"))
for w in d["weekly"]:
    print(f'{w["week"]}: ret={w["return_pct"]}%  held={w["holding"]}')
print()
print(d["summary"])
