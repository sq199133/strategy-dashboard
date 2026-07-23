import json, os, glob
from datetime import datetime

d = r'D:\Qclaw_Trading\data\history_long_v2'
files = sorted(glob.glob(os.path.join(d, '*.json')))

targets = ['2026-W18','2026-W19','2026-W20','2026-W21','2026-W22','2026-W23','2026-W24']
found = {t: [] for t in targets}

for fp in files:
    f = json.load(open(fp, encoding='utf-8', errors='replace'))
    recs = f.get('records', f) if isinstance(f, dict) else f
    for r in recs:
        wk = r.get('w', '') if isinstance(r, dict) else ''
        if wk in found:
            found[wk].append(os.path.basename(fp)[:10])
            
for wk in targets:
    n = len(found[wk])
    print(f'{wk}: {n} files' + (f' (e.g. {found[wk][:3]})' if n else ''))

# Also check: is the backtest even seeing these weeks?
# The backtest builds weeks_set from loaded series
# If a series only has records up to 2026-W17...  
print('\n---')
print(f'Sample: 510880 last w field = {found["2026-W24"][0] if "2026-W24" in found else "not found"}')
