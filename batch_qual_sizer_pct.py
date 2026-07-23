#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch run: percentage-based qual-sizer tests."""
import subprocess, sys, os, json, glob, time
from datetime import datetime

SCRIPT = r'D:\QClaw_Trading\backtest_v5_qual_sizer.py'
REPORT_FILE = r'D:\QClaw_Trading\qual_sizer_pct_results.md'

configs = [
    'none',
    'steppct:0.02:0.50', 'steppct:0.03:0.50', 'steppct:0.05:0.50',
    'steppct:0.08:0.50', 'steppct:0.10:0.50', 'steppct:0.12:0.50', 'steppct:0.15:0.50',
    'steppct:0.03:0.25', 'steppct:0.05:0.25', 'steppct:0.08:0.25', 'steppct:0.10:0.25',
    'linearpct:0.03', 'linearpct:0.05', 'linearpct:0.08', 'linearpct:0.10', 'linearpct:0.15',
]

results = []
total = len(configs)
start_time = time.time()

print(f"Testing {total} percentage-based sizer configs...\n")

for idx, cfg in enumerate(configs):
    t0 = time.time()
    print(f"[{idx+1}/{total}] --qual-sizer {cfg} ...", end=' ', flush=True)
    
    r = subprocess.run([sys.executable, SCRIPT, '--qual-sizer', cfg],
                       capture_output=True, text=True, timeout=600,
                       cwd=r'D:\QClaw_Trading')
    
    if r.returncode != 0:
        print(f"FAILED")
        print(f"  {r.stderr[:300]}")
        continue
    
    # Find most recently modified JSON
    files = glob.glob(os.path.join(r'D:\Qclaw_Trading\backtest_results', 'bt_v5_*.json'))
    if not files:
        print("NO_JSON_OUTPUT")
        continue
    newest = max(files, key=os.path.getmtime)
    
    with open(newest) as f:
        d = json.load(f)
    st = d['stats']
    md = st['max_dd'] * 100 if abs(st['max_dd']) < 1 else st['max_dd']
    
    elapsed = time.time() - t0
    results.append({
        'config': cfg,
        'ann': st['ann_ret'],
        'dd': abs(md),
        'sharpe': st['sharpe'],
        'calmar': st['calmar'],
        'wr': st['win_rate'],
        'total_ret': st['total_ret'],
    })
    print(f"OK ({elapsed:.0f}s) ann={st['ann_ret']:+.1f}% dd={abs(md):.1f}% C={st['calmar']:.2f}")

# Add best absolute from earlier test
results.append({
    'config': 'step:5:0.50 (最佳绝对)',
    'ann': 17.2, 'dd': 18.3, 'sharpe': 0.93, 'calmar': 0.94, 'wr': 43.3, 'total_ret': 1330,
})

total_elapsed = time.time() - start_time
print(f"\nDone in {total_elapsed/60:.1f} min\n")

def dump(records, title, sort_key):
    records = sorted(records, key=sort_key)
    print(f"\n{title}:")
    print(f"{'#':<3} {'Config':<25} {'Ann%':>7} {'DD%':>7} {'S':>5} {'Calmar':>7} {'Win%':>6}")
    print("-"*65)
    for i, r in enumerate(records):
        print(f"{i+1:<3} {r['config']:<25} {r['ann']:>+6.1f}% {r['dd']:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>6.2f} {r['wr']:>5.1f}%")

dump(results, "Calmar排名", lambda x: -x['calmar'])
dump(results, "年化排名", lambda x: -x['ann'])
dump(results, "回撤排名(最小)", lambda x: x['dd'])

# Save results
with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    f.write(f"# 百分比Qual-Sizer测试结果\n")
    f.write(f"测试时间: {datetime.now().isoformat()}\n\n")
    f.write(f"| # | Config | Ann% | DD% | Sharpe | Calmar | Win% |\n")
    f.write(f"|---|--------|:---:|:---:|:-----:|:-----:|:---:|\n")
    for i, r in enumerate(sorted(results, key=lambda x: -x['calmar'])):
        f.write(f"| {i+1} | {r['config']} | {r['ann']:+.1f}% | {r['dd']:.1f}% | {r['sharpe']:.2f} | {r['calmar']:.2f} | {r['wr']:.1f}% |\n")
    f.write(f"\n## 配置说明\n")
    f.write(f"- steppct:P:F: 合格/可用 < P(小数)时仓位降至F\n")
    f.write(f"- linearpct:P: 仓位=min(1, 合格比率/P)\n")

print(f"\nReport: {REPORT_FILE}")
