"""Batch run composite score tests"""
import subprocess, sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

script = r'D:\Qclaw_Trading\backtest_v5_qual_sizer.py'

tests = [
    # (desc, args_list)
    ("Baseline (MA)", ["--end", "2026-W25"]),
    ("SC33-34-33", ["--score-mode", "composite", "--score-w1", "0.33", "--score-w3", "0.34", "--end", "2026-W25"]),
    ("SC33-34-33 noMA", ["--score-mode", "composite", "--score-w1", "0.33", "--score-w3", "0.34", "--no-ma-filter", "--end", "2026-W25"]),
    ("SC20-50-30", ["--score-mode", "composite", "--score-w1", "0.2", "--score-w3", "0.5", "--end", "2026-W25"]),
    ("SC20-50-30 noMA", ["--score-mode", "composite", "--score-w1", "0.2", "--score-w3", "0.5", "--no-ma-filter", "--end", "2026-W25"]),
    ("SC10-40-50", ["--score-mode", "composite", "--score-w1", "0.1", "--score-w3", "0.4", "--end", "2026-W25"]),
    ("SC10-30-60", ["--score-mode", "composite", "--score-w1", "0.1", "--score-w3", "0.3", "--end", "2026-W25"]),
    ("SC40-50-10", ["--score-mode", "composite", "--score-w1", "0.4", "--score-w3", "0.5", "--end", "2026-W25"]),
    ("SC25-50-25", ["--score-mode", "composite", "--score-w1", "0.25", "--score-w3", "0.5", "--end", "2026-W25"]),
    ("SC10-70-20", ["--score-mode", "composite", "--score-w1", "0.1", "--score-w3", "0.7", "--end", "2026-W25"]),
    ("SC10-20-70", ["--score-mode", "composite", "--score-w1", "0.1", "--score-w3", "0.2", "--end", "2026-W25"]),
    ("noMA (no MA filter, default lb3)", ["--no-ma-filter", "--end", "2026-W25"]),
    ("SC30-30-40", ["--score-mode", "composite", "--score-w1", "0.3", "--score-w3", "0.3", "--end", "2026-W25"]),
    ("SC35-35-30", ["--score-mode", "composite", "--score-w1", "0.35", "--score-w3", "0.35", "--end", "2026-W25"]),
]

for i, (desc, args) in enumerate(tests, 1):
    print(f"\n{'='*60}")
    print(f"  [{i}/{len(tests)}] {desc}")
    print(f"{'='*60}")
    sys.stdout.flush()
    
    cmd = [sys.executable, script] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=r'D:\Qclaw_Trading')
    lines = result.stdout.split('\n')
    # Print last 20 lines
    print('\n'.join(lines[-20:]))
    if result.returncode != 0:
        print(f"ERROR (rc={result.returncode}): {result.stderr[-500:]}")
    sys.stdout.flush()

print("\n=== ALL TESTS COMPLETE ===")
