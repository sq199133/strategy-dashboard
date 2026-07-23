#!/usr/bin/env python3
"""Show 2026 weekly from FIXED backtest (sig_week price for buys/sells)"""
import json, sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

RESULT = r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_010854.json'
POOL = r'D:\Qclaw_Trading\data\etf_pool_V1_full.json'

with open(RESULT) as f:
    d = json.load(f)

with open(POOL, encoding='utf-8') as f:
    pool = json.load(f)
nm = {}
for e in pool.get('data', pool.get('etfs', [])):
    nm[e['code']] = e.get('name', e['code']).replace('\u200b','').replace(chr(160),'')

eq = d['equity']
y2026 = [e for e in eq if e['w'].startswith('2026')]
label = d['label']

print(f"{'='*90}")
print(f"  2026 Weekly P&L - {label} (FIXED: trade at sig_week close)")
print(f"{'='*90}")
print(f"{'Week':>12s} {'NAV':>8s} {'WkRet':>8s} {'CumRet':>8s} {'DD':>8s}  {'Holdings'}")
print('-' * 90)

prev = y2026[0]['eq']
total = 1.0
peak = prev

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
    prev = nav

# 2026 summary
w24 = [e for e in y2026 if e['w'] >= '2026-W24']
if w24:
    r_w24 = w24[0]['eq'] / y2026[y2026.index(w24[0])-1]['eq'] - 1 if y2026.index(w24[0]) > 0 else 0
    print(f'\n  W24 yield: {r_w24*100:+.2f}%')
