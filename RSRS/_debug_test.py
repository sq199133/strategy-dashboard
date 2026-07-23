import sys, json, numpy as np, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
sys.stdout.write('=== DEBUG START ===\n')
sys.stdout.flush()

from rsrs_final_strategy import DATA_DIR, load_etf, build_panel, compute_rsrs

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500',
        '512100':'ZZ1000','159915':'CYB','588000':'KC50',
        '513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

raw, panel = build_panel(POOL, min_rows=200)
sys.stdout.write(f'Panel: {len(panel)} days, {panel.index[0].date()} to {panel.index[-1].date()}\n')

df_sig = load_etf('510300')
sys.stdout.write(f'HS300: {len(df_sig)} days, {df_sig.date.iloc[0].date()} to {df_sig.date.iloc[-1].date()}\n')

sig, zs, beta = compute_rsrs(df_sig, 18, 1200, 0.7, -1.0)
nz = sum(1 for z in zs if not np.isnan(z))
ns = sum(1 for s in sig if s==1)
sys.stdout.write(f'Non-nan zscores: {nz}, Signal=1 days: {ns}/{len(sig)}\n')

for i in range(len(zs)):
    if not np.isnan(zs[i]):
        sys.stdout.write(f'First valid zscore at {df_sig.date.iloc[i].date()}, z={zs[i]:.2f}\n')
        break

m_date = df_sig.date.iloc[1200]
sys.stdout.write(f'M=1200 date: {m_date.date()}\n')

# Check 515080
df_515080 = load_etf('515080')
sys.stdout.write(f'515080: {len(df_515080)} days, {df_515080.date.iloc[0].date()} to {df_515080.date.iloc[-1].date()}\n')

sys.stdout.write('=== DEBUG END ===\n')
