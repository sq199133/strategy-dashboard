import sys, os, json, warnings
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
from rsrs_final_strategy import load_etf, compute_rsrs, compute_vol_scaling

df = load_etf('510300')
sig, zs, _ = compute_rsrs(df, 18, 1200, 0.7, -1.0)
last_date = df['date'].iloc[-1]
z = zs[-1]
s = sig[-1]

sc = compute_vol_scaling(df, [last_date], 70, 0.16)
w = float(sc.iloc[-1]) if len(sc) > 0 else 1.0

print(f'DATA_DATE:{last_date.date()}')
print(f'RSRS_Z:{z:.2f}')
print(f'RSRS_SIG:{"LONG" if s==1 else "CASH"}')
print(f'VOL_SCALE:{w:.2f}')
print(f'SUGGEST_POS:{w*100:.0f}')
