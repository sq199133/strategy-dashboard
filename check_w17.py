import json, os, glob

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_000006.json'))
eq = d['equity']
print('First 5:', [e['w'] for e in eq[:5]])
print('Last 5:', [e['w'] for e in eq[-5:]])
print('2026 weeks:', [e['w'] for e in eq if e['w'].startswith('2026-')])

# Check data files for latest week
files = [f for f in os.listdir(r'D:\Qclaw_Trading\data\history_long_v2') if f.endswith('.json')]
print(f'\nTotal data files: {len(files)}')

# Sample a few to find the latest date
latest_dates = []
for fname in sorted(files)[:20]:
    try:
        d2 = json.load(open(os.path.join(r'D:\Qclaw_Trading\data\history_long_v2', fname)))
        recs = d2.get('records', []) if isinstance(d2, dict) else d2
        if recs:
            last = recs[-1]
            ds = last.get('date', '') if isinstance(last, dict) else str(last[0])
            latest_dates.append((fname, ds))
    except:
        pass

# Get actual weeks available
weeks = sorted(set(e['w'] for e in d['equity']))
print(f'\nLast 10 weeks in equity curve: {weeks[-10:]}')

# Is W18 missing because the data ends at W17?
w18_check = [w for w in weeks if 'W18' in w or 'W19' in w]
print(f'W18/W19 in curve: {w18_check}')

# Check: is the range set to 2026-W18 but data only has W17?
import argparse
# Read the params from saved JSON
print(f'\nParams: end={d["params"]["end"]}')
