#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch run: qualified-count-based position sizing
Tests multiple sizer configurations and reports best ones.
"""
import subprocess, sys, os, json, glob, time
from datetime import datetime

SCRIPT = r'D:\QClaw_Trading\backtest_v5_qual_sizer.py'
OUTPUT_DIR = r'D:\QClaw_Trading\backtest_results'
REPORT_FILE = r'D:\QClaw_Trading\qual_sizer_batch_results.md'

# === All sizer configs to test ===
configs = [
    # Baseline
    'none',
    
    # Step: count < N -> F, else 1.0
    'step:2:0.50', 'step:3:0.50', 'step:4:0.50', 'step:5:0.50', 'step:6:0.50', 'step:8:0.50',
    'step:2:0.25', 'step:3:0.25', 'step:4:0.25', 'step:5:0.25',
    'step:2:0.75', 'step:3:0.75', 'step:4:0.75',
    'step:2:0.00', 'step:3:0.00', 'step:4:0.00', 'step:5:0.00',
    
    # Step2: two-tier
    'step2:2:0.50,5:0.75',
    'step2:3:0.50,6:0.75',
    'step2:2:0.25,5:0.50',
    'step2:3:0.25,6:0.50',
    
    # Linear
    'linear:2', 'linear:3', 'linear:4', 'linear:5',
    'linear:6', 'linear:8', 'linear:10',
]

results = []
n_total = len(configs)
n_ok = 0

print(f"Batch testing {n_total} sizer configurations...\n")
start_time = time.time()

for idx, cfg in enumerate(configs):
    t0 = time.time()
    print(f"[{idx+1}/{n_total}] Testing: --qual-sizer {cfg} ...", end=' ', flush=True)
    
    try:
        r = subprocess.run(
            [sys.executable, SCRIPT, '--qual-sizer', cfg],
            capture_output=True, text=True, timeout=600,
            cwd=r'D:\QClaw_Trading'
        )
        
        if r.returncode != 0:
            print(f"FAILED (rc={r.returncode})")
            print(f"  stderr: {r.stderr[:200]}")
            continue
        
        # Parse results
        stats = {}
        for line in r.stdout.split('\n'):
            line_s = line.strip()
            if line_s.startswith('  Total Ret:'):
                stats['total_ret'] = float(line_s.split(':')[1].strip().replace('%',''))
            elif line_s.startswith('  Annual:'):
                stats['ann_ret'] = float(line_s.split(':')[1].strip().replace('%',''))
            elif line_s.startswith('  Max DD:'):
                stats['max_dd'] = float(line_s.split(':')[1].strip().replace('%',''))
            elif line_s.startswith('  Sharpe:'):
                stats['sharpe'] = float(line_s.split(':')[1].strip())
            elif line_s.startswith('  Calmar:'):
                stats['calmar'] = float(line_s.split(':')[1].strip())
            elif line_s.startswith('  Win Rate:'):
                stats['win_rate'] = float(line_s.split(':')[1].strip().replace('%',''))
            elif line_s.startswith('  Avg Qual:'):
                stats['avg_nq'] = float(line_s.split(':')[1].strip().split('/')[0])
        
        elapsed = time.time() - t0
        stats['config'] = cfg
        stats['time_s'] = round(elapsed, 1)
        results.append(stats)
        n_ok += 1
        print(f"OK ({elapsed:.0f}s) ann={stats.get('ann_ret','?'):.1f}% dd={stats.get('max_dd','?'):.1f}%")
        
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT (>10min)")
    except Exception as e:
        print(f"ERROR: {e}")

total_elapsed = time.time() - start_time
print(f"\n{'='*60}")
print(f"Batch complete: {n_ok}/{n_total} OK in {total_elapsed/60:.1f} min")

# Sort results
ranked = sorted(results, key=lambda x: -x.get('sharpe', 0))

# Report
os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(REPORT_FILE, 'w', encoding='utf-8') as f:
    f.write(f"# Qual-Sizer Batch Test Results\n")
    f.write(f"Tested: {datetime.now().isoformat()}\n")
    f.write(f"Parameters: LB=3, D=10, H=2, MA5/21\n\n")
    
    f.write(f"## Ranked by Sharpe Ratio\n\n")
    f.write(f"| # | Config | Ann% | DD% | Sharpe | Calmar | Win% | Total% | AvgQual |\n")
    f.write(f"|---|--------|:---:|:---:|:-----:|:------:|:---:|:-----:|:------:|\n")
    for i, r in enumerate(ranked):
        f.write(f"| {i+1} | {r['config']} | {r.get('ann_ret',0):+.1f}% | {r.get('max_dd',0):.1f}% "
                f"| {r.get('sharpe',0):.2f} | {r.get('calmar',0):.2f} "
                f"| {r.get('win_rate',0):.1f}% | {r.get('total_ret',0):+.1f}% "
                f"| {r.get('avg_nq',0):.0f} |\n")
    
    f.write(f"\n## Ranked by Annual Return\n\n")
    ranked_by_ann = sorted(results, key=lambda x: -x.get('ann_ret', 0))
    f.write(f"| # | Config | Ann% | DD% | Sharpe | Calmar | Win% |\n")
    f.write(f"|---|--------|:---:|:---:|:-----:|:------:|:---:|\n")
    for i, r in enumerate(ranked_by_ann[:20]):
        f.write(f"| {i+1} | {r['config']} | {r.get('ann_ret',0):+.1f}% | {r.get('max_dd',0):.1f}% "
                f"| {r.get('sharpe',0):.2f} | {r.get('calmar',0):.2f} | {r.get('win_rate',0):.1f}% |\n")
    
    f.write(f"\n## Ranked by Max DD (lowest best)\n\n")
    ranked_by_dd = sorted(results, key=lambda x: x.get('max_dd', 999))
    f.write(f"| # | Config | DD% | Ann% | Sharpe | Calmar |\n")
    f.write(f"|---|--------|:---:|:---:|:-----:|:-----:|\n")
    for i, r in enumerate(ranked_by_dd[:20]):
        f.write(f"| {i+1} | {r['config']} | {r.get('max_dd',0):.1f}% | {r.get('ann_ret',0):+.1f}% "
                f"| {r.get('sharpe',0):.2f} | {r.get('calmar',0):.2f} |\n")
    
    f.write(f"\n## Config descriptions\n")
    f.write(f"- **none**: Baseline (no sizing, 100% allocation)\n")
    f.write(f"- **step:N:F**: When qualified count < N, scale to fraction F. Else 100%\n")
    f.write(f"- **step2:N1:F1,N2:F2**: Two-tier: <N1: F1, <N2: F2, else 100%\n")
    f.write(f"- **linear:N**: factor = min(1.0, count/N)\n")

print(f"\nReport saved: {REPORT_FILE}")
print(f"\nTop 10 by Sharpe:")
for i, r in enumerate(ranked[:10]):
    print(f"  {i+1}. {r['config']:20s} ann={r.get('ann_ret','?'):>+6.1f}% dd={r.get('max_dd','?'):>5.1f}% Sharpe={r.get('sharpe','?'):>5.2f}")
