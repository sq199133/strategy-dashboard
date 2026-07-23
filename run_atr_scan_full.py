"""Batch ATR filter scan on full 190-ETF dataset"""
import subprocess, json, sys, re, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

base = r'D:\Qclaw_Trading\backtest_v5_qual_sizer.py'
results = []

thresholds = [None, 0.75, 0.80, 0.85, 0.90, 0.95]

common = ['--score-mode', 'composite', '--score-w1', '0.4', '--score-w3', '0.4', '--max-dev', '15', '--top-n', '3']

for thr in thresholds:
    cmd = [sys.executable, base] + common
    label = 'baseline'
    if thr is not None:
        cmd += ['--atr-filter', str(thr)]
        label = f'ATRf{thr:.2f}'
    
    print(f'\n>>> {label}')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = r.stdout
    
    # Parse
    ann = mdd = sharpe = calmar = win = total = y2026 = avgq = nb = ns = None
    for line in out.split('\n'):
        ls = line.strip()
        if 'Annual:' in line: ann = float(line.split()[-1].replace('%',''))
        elif 'Max DD:' in line: mdd = float(line.split()[-1].replace('%',''))
        elif 'Sharpe:' in line: sharpe = float(line.split()[-1])
        elif 'Total Ret:' in line: total = float(line.split()[-1].replace('%',''))
        elif 'Calmar:' in line: calmar = float(line.split()[-1])
        elif 'Win Rate:' in line: win = float(line.split()[-1].replace('%',''))
        elif 'Trades:' in line:
            import re
            m = re.search(r'Trades:\s+(\d+)B\s+/\s+(\d+)S', line)
            if m:
                nb = int(m.group(1))
                ns = int(m.group(2))
        elif 'Avg Qual:' in line: avgq = float(line.split()[2].split('/')[0])
        elif ls.startswith('2026'):
            parts = line.strip().split()
            if len(parts) >= 2:
                y2026 = float(parts[1].replace('%',''))
    
    results.append((label, ann, sharpe, mdd, calmar, win, y2026, nb, ns, avgq))

print('\n\n' + '='*90)
print(f'  ATR FILTER SCAN - Full 190 ETF Dataset')
print(f'='*90)
print(f'{"Config":<20} {"Ann":>7} {"Sharpe":>7} {"DD":>7} {"Calmar":>7} {"Win%":>6} {"2026":>7} {"Trades":>8} {"Q":>5}')
print(f'{"-"*90}')
for r in results:
    print(f'{r[0]:<20} {r[1]:>+6.1f}% {r[2]:>6.2f} {r[3]:>6.1f}% {r[4]:>6.2f} {r[5]:>5.1f}% {r[6]:>+6.1f}% {r[7]:>4d}/{r[8]:<3d} {r[9]:>4.0f}')
