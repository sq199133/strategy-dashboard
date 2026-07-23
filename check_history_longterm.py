#!/usr/bin/env python3
"""Extract long-history files from history/ directory"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

hist_dir = r'D:\QClaw_Trading\data\history'
out_dir = r'D:\QClaw_Trading\data\history_long'

long_files = []
for fname in sorted([f for f in os.listdir(hist_dir) if f.endswith('.json')]):
    fpath = os.path.join(hist_dir, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) >= 500:
            first = data[0]
            last = data[-1]
            if isinstance(first, dict) and 'date' in first:
                long_files.append((fname, len(data), first['date'], last['date']))
    except:
        pass

print('Long-history files (>=500 days): {}'.format(len(long_files)))
for fname, rows, d0, d1 in long_files[:10]:
    print('  {}: {} rows, {}~{}'.format(fname, rows, d0, d1))

# Check if ETF pool codes are in history/
print('\nKey ETF codes availability:')
import json as j
pool_path = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
with open(pool_path, 'r', encoding='utf-8') as f:
    pool = j.load(f)
etfs = pool.get('data', pool.get('etfs', []))
found = 0
not_found = 0
for etf in etfs:
    code = etf['code']
    if os.path.exists(os.path.join(hist_dir, code + '.json')):
        found += 1
    else:
        not_found += 1
print('  In history/: {} / {} ETFs'.format(found, len(etfs)))
print('  Missing: {} ETFs'.format(not_found))
