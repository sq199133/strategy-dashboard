import sys, warnings, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import load_etf, compute_rsrs

df = load_etf('510300')
sig, zs, beta = compute_rsrs(df, 18, 1200, 0.7, -1.0)
dates = [str(d)[:10] for d in df['date'].values]

# last 6 non-nan
count = 0
for i in range(len(zs)-1, -1, -1):
    if not np.isnan(zs[i]):
        print(f'Last: {dates[i]} z={zs[i]:.2f} sig={int(sig[i])}')
        count += 1
        if count >= 6:
            break
