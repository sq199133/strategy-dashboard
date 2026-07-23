"""Check how many ETFs are available at each year for long-term backtesting"""
import json, os, pandas as pd

data_dir = 'D:/QClaw_Trading/data/history/'

# Collect all ETFs and their date ranges
min_hist = {}
for fname in os.listdir(data_dir):
    if not fname.endswith('.json'):
        continue
    code = fname[:-5]
    if code[:3] not in ('159','510','511','512','513','515','516','517','518',
                        '560','561','562','563','588'):
        if code[:2] not in ('51','56','58'):
            continue
    with open(os.path.join(data_dir, fname), encoding='utf-8') as f:
        raw = json.load(f)
    records = raw.get('records', [])
    if len(records) < 60:
        continue
    min_hist[code] = {
        'start': records[0]['date'],
        'end': records[-1]['date'],
        'n': len(records)
    }

# Count ETFs available at each year (need 1 year warmup)
print("Available ETFs at each year (need factor by Jan of that year):")
for year in range(2010, 2027):
    cutoff = f'{year-1}-01-01'
    count = sum(1 for v in min_hist.values() if v['start'] <= cutoff and v['n'] >= 252)
    print(f"  {year}: {count} ETFs")

# Top 30 oldest ETFs
print("\nOldest ETFs:")
etfs_sorted = sorted(min_hist.items(), key=lambda x: x[1]['start'])
for code, info in etfs_sorted[:30]:
    print(f"  {code}: {info['start']} ~ {info['end']} ({info['n']} records)")

# Check if there are enough ETFs for a 10-year backtest
long_enough = [(c,i) for c,i in min_hist.items() if i['n'] >= 252 and i['start'] <= '2013-01-01']
print(f"\nETFs with data from 2013 or earlier: {len(long_enough)}")
for code, info in long_enough[:20]:
    print(f"  {code}: {info['start']} ~ {info['end']} ({info['n']} records)")
