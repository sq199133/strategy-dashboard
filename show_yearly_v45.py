#!/usr/bin/env python3
"""Comprehensive yearly breakdown: return, win rate, trades, holdings, sharpe"""
import json, os, sys, statistics
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load saved result
fp = r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260617_233238.json'
with open(fp, encoding='utf-8') as f:
    data = json.load(f)

eq_curve = data['equity']
stats = data['stats']
params = data['params']
label = data['label']

print(f'Strategy: {label}')
print(f'Period: {eq_curve[0]["w"]} ~ {eq_curve[-1]["w"]}')
print(f'Total Ret: {stats["total_ret"]:+.1f}%  Annual: {stats["ann_ret"]:+.1f}%  DD: {stats["max_dd"]*100:.1f}%  Sharpe: {stats["sharpe"]:.2f}')
print()

# Group by year
from collections import defaultdict
yearly = defaultdict(list)
for e in eq_curve:
    yr = e['w'][:4]
    yearly[yr].append(e)

print(f"{'Year':<6} {'Ret':>7} {'DD':>7} {'Win%':>5} {'Buys':>5} {'Sells':>5} {'Trades':>7} {'Hold%':>6} {'Sharpe':>7} {'AvgQual':>7}")
print(f"{'─'*70}")

for yr in sorted(yearly):
    es = yearly[yr]
    n = len(es)
    if n < 2 or es[0]['eq'] <= 0:
        continue

    # Return
    ret = (es[-1]['eq'] / es[0]['eq'] - 1) * 100

    # Max DD (within year)
    pk = es[0]['eq']
    yr_dd = 0
    for e in es:
        if e['eq'] > pk: pk = e['eq']
        dd = (e['eq'] / pk - 1) * 100
        if dd < yr_dd: yr_dd = dd

    # Weekly win rate
    w_rets = []
    for i in range(1, n):
        if es[i-1]['eq'] > 0:
            w_rets.append(es[i]['eq'] / es[i-1]['eq'] - 1)
    win_rate = sum(1 for r in w_rets if r > 0) / len(w_rets) * 100 if w_rets else 0

    # Weekly sharpe (within year)
    if len(w_rets) > 1:
        avg_r = statistics.mean(w_rets)
        std_r = statistics.stdev(w_rets)
        yr_sharpe = (avg_r * 52 - 0.02) / (std_r * 52**0.5) if std_r > 0 else 0
    else:
        yr_sharpe = 0

    # Trades - estimate from NH changes
    n_buys = 0
    n_sells = 0
    for i in range(1, n):
        diff = es[i]['nh'] - es[i-1]['nh']
        # nh counts positions held; track changes approximately
    # We can count sells from the "h" field changes
    prev_holds = set(es[0].get('h', []))
    for i in range(1, n):
        cur_holds = set(es[i].get('h', []))
        sold = prev_holds - cur_holds
        bought = cur_holds - prev_holds
        # Only count non-overlap (one sell can free slot for one buy)
        net_sells = len(sold)
        net_buys = len(bought)
        n_sells += net_sells
        n_buys += net_buys
        prev_holds = cur_holds

    # Holdings
    avg_nh = statistics.mean(e['nh'] for e in es)
    hold_pct = avg_nh / params.get('top_n', 3) * 100

    # Avg qualified
    nqs = [e.get('nq', 0) for e in es]
    avg_nq = statistics.mean(nqs) if nqs else 0

    print(f"{yr:<6} {ret:>+6.1f}% {yr_dd:>6.1f}% {win_rate:>4.0f}% {n_buys:>5} {n_sells:>5} {n_buys+n_sells:>5}T {hold_pct:>5.0f}% {yr_sharpe:>6.2f} {avg_nq:>5.0f}", end='')
    print()
