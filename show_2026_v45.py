#!/usr/bin/env python3
"""Show 2026 weekly breakdown from latest full backtest"""
import json, sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

RESULT = r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_010151.json'
POOL = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'

with open(RESULT) as f:
    d = json.load(f)

# Load names
with open(POOL, encoding='utf-8') as f:
    pool = json.load(f)
nm = {}
for e in pool.get('data', pool.get('etfs', [])):
    nm[e['code']] = e.get('name', e['code']).replace('\u200b','').replace(chr(160),'')

eq = d['equity']
y2026 = [e for e in eq if e['w'].startswith('2026')]
label = d['label']

print(f"{'='*90}")
print(f"  2026 Weekly P&L - {label} (full data, --end 2026-W30)")
print(f"{'='*90}")
print(f"{'Week':>12s} {'NAV':>8s} {'WkRet':>8s} {'CumRet':>8s} {'DD':>8s}  {'Holdings'}")
print('-' * 90)

prev = y2026[0]['eq']
total = 1.0
peak = prev
pos = neg = 0

for e in y2026:
    nav = e['eq']
    r = nav/prev - 1 if prev else 0
    total *= (1+r)
    if nav > peak: peak = nav
    dd = (nav/peak - 1)*100
    codes = e['h'] or []
    holds = ', '.join([f'{c}({nm.get(c,c)})' for c in codes]) if codes else '(空仓)'
    ws = f'{r*100:+6.2f}%' if prev else '   ---'
    cs = f'{(total-1)*100:+6.2f}%'
    ds = f'{dd:6.1f}%'
    print(f'{e["w"]:>12s}  {nav:>7.4f}  {ws:>7s}  {cs:>7s}  {ds:>7s}  {holds}')
    if r:
        if r>0: pos+=1
        else: neg+=1
    prev = nav

print()
print(f'YTD: {(total-1)*100:+.2f}%  正周{pos} 负周{neg}  最大回撤{min([(n["eq"]/max([x["eq"] for x in y2026[:i+1]])-1)*100 for i,n in enumerate(y2026)]):.1f}%')
