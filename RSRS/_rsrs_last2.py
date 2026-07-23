import sys, warnings, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import load_etf, compute_rsrs

df = load_etf('510300')
sig, zs, beta = compute_rsrs(df, 18, 1200, 0.7, -1.0)
dates = [str(d)[:10] for d in df['date'].values]

with open(r'D:\QClaw_Trading\RSRS\_rsrs_last_out.txt', 'w', encoding='utf-8') as f:
    f.write(f'Total rows: {len(df)}\n')
    f.write(f'Last date: {dates[-1]}\n')
    f.write(f'Last z: {zs[-1]:.4f}\n')
    f.write(f'Last sig: {int(sig[-1])}\n\n')
    count = 0
    for i in range(len(zs)-1, -1, -1):
        if not np.isnan(zs[i]):
            mode = 'LONG' if sig[i]==1 else 'CASH'
            f.write(f'{dates[i]}: z={zs[i]:.2f} [{mode}]\n')
            count += 1
            if count >= 8:
                break
    f.write(f'\nRSRS trend (last 30 non-nan):\n')
    count = 0
    for i in range(len(zs)-1, -1, -1):
        if not np.isnan(zs[i]):
            mode = 'LONG' if sig[i]==1 else 'CASH'
            f.write(f'{dates[i]} z={zs[i]:+.2f} {mode}\n')
            count += 1
            if count >= 30:
                break
