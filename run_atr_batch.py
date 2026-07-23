"""Batch ATR tests"""
import sys, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

base = r'D:\Qclaw_Trading\test_atr_factor.py'
results = []

tests = [
    # Baseline
    [],
    # ATR filter thresholds
    ['--atr-filter', '0.80'],
    ['--atr-filter', '0.85'],
    ['--atr-filter', '0.90'],
    ['--atr-filter', '0.95'],
    # ATR boost weights
    ['--atr-boost', '0.2'],
    ['--atr-boost', '0.5'],
    ['--atr-boost', '1.0'],
    ['--atr-boost', '2.0'],
    # Combined: filter light + boost
    ['--atr-filter', '0.85', '--atr-boost', '0.3'],
    ['--atr-filter', '0.85', '--atr-boost', '0.5'],
    ['--atr-filter', '0.90', '--atr-boost', '0.3'],
]

for test_args in tests:
    cmd = ['python', base] + test_args
    label = 'none'
    for i, a in enumerate(test_args):
        if a.startswith('--atr'):
            label = a.split('--')[1]
    
    print(f"\n>>> Running: {label} {' '.join(test_args)}")
    print('-' * 50)
    
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = r.stdout
    
    # Parse results
    ann = sharpe = mdd = calmar = win = total = None
    y2026 = None
    for line in out.split('\n'):
        line = line.strip()
        if 'Annual:' in line:
            ann = float(line.split()[-1].replace('%',''))
        elif 'Max DD:' in line:
            mdd = float(line.split()[-1].replace('%',''))
        elif 'Sharpe:' in line:
            sharpe = float(line.split()[-1])
        elif 'Total Ret:' in line:
            total = float(line.split()[-1].replace('%',''))
        elif 'Calmar:' in line:
            calmar = float(line.split()[-1])
        elif 'Win Rate:' in line:
            win = float(line.split()[-1].replace('%',''))
        elif '2026' in line and line.strip().startswith('2026'):
            y2026 = float(line.split()[-1].replace('%',''))
    
    results.append({
        'label': label if label != 'none' else 'baseline',
        'args': test_args,
        'ann': ann,
        'mdd': mdd,
        'sharpe': sharpe,
        'calmar': calmar,
        'win': win,
        'total': total,
        'y2026': y2026,
    })

    # Print summary
    y26_str = f'{y2026:+.1f}%' if y2026 is not None else 'N/A'
    print(f"  → Ann={ann:+.1f}% Sharpe={sharpe:.2f} DD={mdd:.1f}% Calmar={calmar:.2f} 2026={y26_str}")

print(f"\n\n{'='*70}")
print(f"  ATR FACTOR TEST - COMPARISON TABLE")
print(f"{'='*70}")
print(f"{'Config':<30} {'Ann':>7} {'Sharpe':>7} {'DD':>7} {'Calmar':>7} {'2026':>7} {'Total':>7}")
print(f"{'-'*70}")
for r in results:
    print(f"{r['label']:<30} {r['ann']:>+6.1f}% {r['sharpe']:>6.2f} {r['mdd']:>6.1f}% {r['calmar']:>6.2f} {r['y2026']:>+6.1f}% {r['total']:>+6.0f}%")
