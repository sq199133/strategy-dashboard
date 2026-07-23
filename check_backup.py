#!/usr/bin/env python3
"""Check history_long backup data quality"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

backup_dir = r'D:\QClaw_Trading\data\history_long_backup_20260613'

files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.json')])
print('Total: {} JSON files'.format(len(files)))

# Count by data range
good = 0
short = 0
for fname in sorted(files):
    fpath = os.path.join(backup_dir, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            last = data[-1]
            if isinstance(first, dict):
                weeks = len(data)
                if weeks >= 200:
                    good += 1
                else:
                    short += 1
        else:
            pass
    except:
        pass

print('Good (>=200 weeks): {}'.format(good))
print('Short (<200 weeks): {}'.format(short))

# Show detail for key ETFs
key_codes_files = []
for c in ['510880', '159915', '513500', '159981', '588910', '562500', '517850']:
    for p in ['sh', 'sz']:
        f = os.path.join(backup_dir, '{}{}.json'.format(p, c))
        if os.path.exists(f):
            key_codes_files.append(f)

print('\nKey ETFs:')
for fpath in key_codes_files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            last = data[-1]
            fname = os.path.basename(fpath)
            if isinstance(first, dict):
                print('  {}: {} weeks, {}~{}'.format(
                    fname, len(data), first.get('w','?'), last.get('w','?')))
            else:
                print('  {}: {} records, type={}'.format(fname, len(data), type(first).__name__))
    except Exception as e:
        print('  {}: error'.format(os.path.basename(fpath)))
