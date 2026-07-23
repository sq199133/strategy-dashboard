#!/usr/bin/env python3
"""显示逐年收益率"""
import json
from collections import defaultdict

def show_yearly(data, label):
    equity = data.get('equity', [])
    yg = defaultdict(list)
    for e in equity:
        yr = e['w'][:4]
        yg[yr].append(e)

    print(f"\n{'='*70}")
    print(f"{label} 逐年收益率（2010-2026）")
    print(f"{'='*70}")
    print(f"{'Year':<6} {'Start':>10} {'End':>10} {'Return':>8} {'MaxDD':>8} {'Hold%':>6}")
    print(f"{'-'*70}")

    all_rets = []
    for yr in sorted(yg):
        es = yg[yr]
        if not es:
            continue

        start_eq = es[0]['eq']
        end_eq = es[-1]['eq']
        ret = (end_eq / start_eq - 1) * 100
        all_rets.append(ret)

        peak = start_eq
        max_dd = 0
        hold_sum = 0
        for e in es:
            if e['eq'] > peak:
                peak = e['eq']
            dd = (e['eq'] / peak - 1) * 100
            if dd < max_dd:
                max_dd = dd
            hold_sum += e.get('nh', 0)

        hold_pct = hold_sum / len(es) / 3 * 100

        print(f"{yr:<6} {start_eq:>10.4f} {end_eq:>10.4f} {ret:>+7.1f}% {max_dd:>7.1f}% {hold_pct:>5.0f}%")

    # Summary
    print(f"{'-'*70}")
    print(f"Total: {len(all_rets)} years")
    pos = [r for r in all_rets if r > 0]
    neg = [r for r in all_rets if r < 0]
    print(f"Positive: {len(pos)} years, Negative: {len(neg)} years")
    print(f"Average: {sum(all_rets)/len(all_rets):+.1f}%")

# 第1名
with open('D:/QClaw_Trading/backtest_results/verify_5_21_3_10_2.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
show_yearly(data, "MA5/21 LB3 D10 H2 (Rank 1)")

# 第2名
with open('D:/QClaw_Trading/backtest_results/verify_5_21_3_10_3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
show_yearly(data, "MA5/21 LB3 D10 H3 (Rank 2)")

# 第3名
with open('D:/QClaw_Trading/backtest_results/verify_5_21_4_10_3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
show_yearly(data, "MA5/21 LB4 D10 H3 (Rank 3)")
