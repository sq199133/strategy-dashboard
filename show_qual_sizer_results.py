#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse and present qual-sizer batch results."""
import json, glob, os

result_dir = r'D:\QClaw_Trading\backtest_results'
files = sorted(glob.glob(os.path.join(result_dir, 'bt_v5_*.json')))

records = []
for fp in files:
    with open(fp) as f:
        d = json.load(f)
    st = d['stats']
    label = d.get('label', '')
    if '+QS:' in label:
        cfg = label.split('+QS:')[1]
    else:
        cfg = 'none'
    
    # Fix: max_dd is stored as decimal fraction in JSON (e.g. -0.18 = -18%)
    max_dd_val = st['max_dd']
    if abs(max_dd_val) < 1:
        max_dd_val = max_dd_val * 100
    
    records.append({
        'config': cfg,
        'ann': st['ann_ret'],
        'dd': abs(max_dd_val),
        'sharpe': st['sharpe'],
        'calmar': st['calmar'],
        'win_rate': st['win_rate'],
        'total_ret': st['total_ret'],
    })

# Add baseline from original backtest
records.append({
    'config': 'BASELINE (无择时)',
    'ann': 18.6, 'dd': 27.2, 'sharpe': 0.93, 'calmar': 0.68,
    'win_rate': 43.3, 'total_ret': 1441.4,
})

print("="*85)
print("QUAL-SIZER 大规模测试结果 (29个配置 x 17年回测)")
print("="*85)

print(f"\n综合排名 (按 Calmar 比率 = 年化/回撤，越高越好)")
print("-"*65)
print(f"{'排名':<4} {'配置':<25} {'年化':>7} {'回撤':>7} {'夏普':>6} {'Calmar':>7} {'胜率':>6}")
print("-"*65)
ranked = sorted(records, key=lambda x: -x['calmar'])
for i, r in enumerate(ranked):
    print(f"{i+1:<4} {r['config']:<25} {r['ann']:>+6.1f}% {r['dd']:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>6.2f} {r['win_rate']:>5.1f}%")

print(f"\n按年化收益排名")
print("-"*55)
by_ann = sorted(records, key=lambda x: -x['ann'])
for i, r in enumerate(by_ann):
    print(f"{i+1:<4} {r['config']:<25} {r['ann']:>+6.1f}% {r['dd']:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>6.2f}")

print(f"\n按最大回撤排名 (风险最低)")
print("-"*55)
by_dd = sorted(records, key=lambda x: x['dd'])
for i, r in enumerate(by_dd):
    print(f"{i+1:<4} {r['config']:<25} {r['ann']:>+6.1f}% {r['dd']:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>6.2f}")

print(f"\n{'='*85}")
print("关键结论")
print(f"{'='*85}")
print("""
1. 没有任何qual-sizer能提高年化收益 — 基线(+18.6%)仍然是最高收益
2. 最好的平衡方案: step:5:0.50 (合格ETF < 5只时半仓)
   - 年化+17.2% (只比基线低1.4%)
   - 回撤从-27.2% 降至 -18.3% (减少8.9%)
   - Calmar从0.68提升至0.94 (风险收益比大幅改善)
   - 夏普0.93 vs 基线0.93 (完全一样)
3. 最激进回撤控制: step:5:0.25 (合格<5只时25%仓位)
   - 回撤降至-17.9%
   - 年化+16.4%
4. 多级降仓(step2)和线性降仓(linear)效果均不如单级step
5. 核心逻辑: 合格ETF数量少=市场动量弱，减仓是有效的风控手段
""")
