import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('D:/Qclaw_Trading/data/etf_pool_V1_full.json', encoding='utf-8') as f:
    data = json.load(f)

etfs = data.get('data', data.get('etfs', []))

cats = {}
for e in etfs:
    cat = e.get('category', '?')
    cats.setdefault(cat, []).append(e['code'] + ' ' + e['name'])

for cat in sorted(cats.keys()):
    print(f'\n=== {cat} ({len(cats[cat])}只) ===')
    for name in sorted(cats[cat]):
        try:
            print(f'  {name}')
        except Exception:
            print(f'  {name.encode("utf-8","replace").decode("utf-8")}')

print(f'\n总ETF数: {len(etfs)}')
