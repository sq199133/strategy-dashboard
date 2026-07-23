import json, os, glob
from datetime import datetime
from collections import Counter

d = r'D:\Qclaw_Trading\data\history_long_v2'
files = [f for f in os.listdir(d) if f.endswith('.json')]

# Count how many ETFs have data for each 2026 week
week_count = Counter()
year_weeks = set()

for idx, fname in enumerate(sorted(files)):
    if idx >= 50:  # sample 50 files
        break
    try:
        f = json.load(open(os.path.join(d, fname)))
        recs = f.get('records', f) if isinstance(f, dict) else f
        for r in recs:
            ds = r.get('date', r[0]) if isinstance(r, dict) else r[0]
            dt = datetime.strptime(ds, '%Y-%m-%d')
            y, w, _ = dt.isocalendar()
            wk = f'{y}-W{w:02d}'
            if y == 2026:
                year_weeks.add(wk)
                week_count[wk] += 1
    except:
        pass

print(f'2026 weeks found (from {len(files)} files):')
for wk in sorted(year_weeks):
    print(f'  {wk}: {week_count[wk]}/50+ files')
