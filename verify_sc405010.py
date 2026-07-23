#!/usr/bin/env python3
"""Re-run SC40-50-10 backtest and check 2026 weekly details"""
import sys
sys.path.insert(0, r'D:\Qclaw_Trading')

# Import the backtest module
from importlib import import_module

# Just run the backtest directly
import subprocess
result = subprocess.run([
    sys.executable, r'D:\Qclaw_Trading\backtest_v5_qual_sizer.py',
    '--score-mode', 'composite',
    '--score-w1', '0.4',
    '--score-w3', '0.5',
    '--label', 'SC405010_check'
], capture_output=True, text=True, encoding='utf-8', cwd=r'D:\Qclaw_Trading')
print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[-1000:])
