import sys, os, warnings
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rsrs_final_strategy import load_etf, build_panel
import pandas as pd, numpy as np

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

raw, panel = build_panel(POOL, min_rows=200)
dt = panel.index[-1]
print(f'C63 Ranking @ {dt.date()}:')
print(f'  {"Code":<10} {"Name":<6} {"C63":>8} {"12-1":>8}')

results = []
for code, name in POOL.items():
    if dt in raw[code].set_index('date').index:
        dfi = raw[code].set_index('date')
        c63 = dfi['close'].pct_change(63).loc[dt]
        lag1m = 21; lag12m = 252
        if len(dfi) >= lag12m:
            p1 = dfi['close'].shift(lag1m).loc[dt]
            p2 = dfi['close'].shift(lag12m).loc[dt]
            m121 = (p1/p2 - 1) if (not np.isnan(p1) and not np.isnan(p2) and p2 > 0) else np.nan
        else:
            m121 = np.nan
        results.append((code, name, c63, m121))

results.sort(key=lambda x: -x[2] if not np.isnan(x[2]) else -999)
for code, name, c63, m121 in results:
    c63_str = f'{c63*100:>7.1f}%' if not np.isnan(c63) else '  N/A  '
    m121_str = f'{m121*100:>7.1f}%' if not np.isnan(m121) else '  N/A  '
    star = ' <=' if code == '588000' else ''
    print(f'  {code:<10} {name:<6} {c63_str} {m121_str}{star}')
