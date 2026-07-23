#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

hl_dir = r'D:\QClaw_Trading\data\history_long'
files = [f for f in os.listdir(hl_dir) if f.endswith('.json')]
old_prefixed = [f for f in files if f.startswith(('sh', 'sz'))]

print(f'Deleting {len(old_prefixed)} old prefixed files...')
for f in old_prefixed:
    os.remove(os.path.join(hl_dir, f))
print('Done.')

remaining = [f for f in os.listdir(hl_dir) if f.endswith('.json')]
log_exists = os.path.exists(os.path.join(hl_dir, 'download_log_tx.txt'))
print(f'Remaining JSON files: {len(remaining)}')
print(f'Log file exists: {log_exists}')

# Quick verification of key ETFs
import json
for code in ['510880', '159915', '513500', '159981', '518880', '513400', '588000', '562500']:
    fpath = os.path.join(hl_dir, code + '.json')
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            print(f'{code}: {len(data)} weeks, {data[0]["date"]} ~ {data[-1]["date"]}')
        else:
            print(f'{code}: wrong format')
    else:
        print(f'{code}: MISSING')
