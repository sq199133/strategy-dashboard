# -*- coding: utf-8 -*-
"""Quick diagnostic: check data loading and candidate counts"""
import json, glob, os
from datetime import datetime as dt

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

with open(POOL_FILE, encoding='utf-8') as f:
    pool_data = json.load(f)
etfs = pool_data if isinstance(pool_data, list) else pool_data.get('data', [])
print(f"ETFs in pool: {len(etfs)}")
if etfs:
    print(f"  First ETF: {etfs[0]}")

# Load data using batch script's method
series = {}
weeks_set = set()
loaded = 0
for etf in etfs:
    code = etf['code']
    for pat in [code, f'sh{code}', f'sz{code}', code[2:]]:
        matches = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not matches:
            matches = glob.glob(os.path.join(HISTORY_DIR, f'*{code}.json'))
        if matches:
            try:
                with open(matches[0], encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d.get('records', []) if isinstance(d, dict) else d
                if not recs:
                    break
                if isinstance(recs[0], list):
                    recs = [{'date': r[0], 'close': r[4], 'open': r[1], 'high': r[2], 'low': r[3], 'vol': r[5]} for r in recs]
                elif 'w' in recs[0]:
                    recs = [{'date': r.get('date', ''), 'open': r.get('open', r['close']), 'high': r.get('high', r['close']), 'low': r.get('low', r['close']), 'close': r['close'], 'vol': r.get('vol', 0)} for r in recs]
                weeks = {}
                for r in recs:
                    ds = r.get('date', '')
                    if not ds:
                        continue
                    try:
                        y, wn, _ = dt.strptime(ds, '%Y-%m-%d').isocalendar()
                        wk = f'{y}-W{wn:02d}'
                        if wk not in weeks or ds > weeks[wk][0]:
                            weeks[wk] = (ds, r['close'])
                    except:
                        pass
                sorted_wks = sorted(weeks.items())
                series[code] = [(wk, cl) for wk, (_, cl, *_) in sorted_wks]
                weeks_set.update(wk for wk, _ in sorted_wks)
                loaded += 1
            except Exception as e:
                print(f"  ERROR loading {code}: {e}")
            break

print(f"\nLoaded: {loaded}/{len(etfs)} ETFs")
all_weeks = sorted(weeks_set)
print(f"Weeks: {len(all_weeks)}, {all_weeks[0]} ~ {all_weeks[-1]}")

# Check a few series
for code in list(series.keys())[:3]:
    s = series[code]
    print(f"  {code}: {len(s)} weeks, first={s[0]}, last={s[-1]}")
    if len(s) > 0 and isinstance(s[0][1], tuple):
        print(f"    !!! s[0][1] is tuple: {s[0][1]}")

# Count candidates in week 500
mid = all_weeks[500] if len(all_weeks) > 500 else all_weeks[-1]
print(f"\nCandidates in week {mid}:")
ma_l = 21
first_avail = {c: (s[ma_l][0] if len(s) >= ma_l+1 else None) for c, s in series.items()}
c = 0
for code, s in series.items():
    if first_avail.get(code) and first_avail[code] > mid:
        continue
    idx = None
    for j, (wk, _) in enumerate(s):
        if wk == mid:
            idx = j; break
    if idx is None or idx < 21:
        continue
    price = s[idx][1]
    if price is None:
        continue
    ma5_list  = [s[j][1] for j in range(idx-4, idx+1)]
    ma21_list = [s[j][1] for j in range(idx-20, idx+1)]
    if None in ma5_list or None in ma21_list:
        print(f"  {code}: MA contains None")
        continue
    if any(isinstance(x, tuple) for x in ma5_list):
        print(f"  {code}: MA data contains tuples! s[{idx-4}][1]={s[idx-4][1]}")
        continue
    ma5  = sum(ma5_list) / 5
    ma21 = sum(ma21_list) / 21
    if ma21 == 0:
        continue
    dev = abs(price / ma21 - 1) * 100
    if dev > 15.0:
        continue
    c += 1
print(f"  Total: {c} out of {len(series)}")
