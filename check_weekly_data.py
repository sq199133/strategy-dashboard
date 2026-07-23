#!/usr/bin/env python3
"""Check raw weekly data for specific ETFs"""
import json, os

DATA_DIR = r'D:\Qclaw_Trading\data\history_long_v2'

for code in ['510880', '513400', '159981']:
    f = os.path.join(DATA_DIR, f'{code}.json')
    if not os.path.exists(f):
        print(f'{code}: file not found')
        continue
    with open(f) as fp:
        d = json.load(fp)
    if isinstance(d, dict):
        recs = d.get('records', [])
    else:
        recs = d
    
    # Find 2026-W24 and W25
    print(f'\n=== {code} ===')
    found = False
    for r in recs[-5:]:
        w = r.get('w', '?')
        close = r.get('close', 0)
        date = r.get('date_end', r.get('date', '?'))
        print(f'  {w:>12s} {date}  close={close:.4f}')
    
    # Check W24 specifically
    for r in recs:
        if r.get('w') in ['2026-W24', '2026-W25']:
            close = r.get('close', 0)
            prev = None
            # find prev week
            idx = recs.index(r)
            if idx > 0:
                prev = recs[idx-1].get('close', 0)
            wkret = (close/prev - 1)*100 if prev else None
            print(f'  >> {r["w"]} close={close:.4f} wk_ret={wkret:.2f}%' if wkret else f'  >> {r["w"]} close={close:.4f}')
