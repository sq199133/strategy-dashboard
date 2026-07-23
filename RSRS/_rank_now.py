import sys, warnings, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import load_etf, build_panel

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

raw, panel = build_panel(POOL, min_rows=200)
dt = panel.index[-1]

results = []
for code, name in POOL.items():
    if dt in raw[code].set_index('date').index:
        dfi = raw[code].set_index('date')
        c63 = dfi['close'].pct_change(63).loc[dt]
        c21 = dfi['close'].pct_change(21).loc[dt]
        c5  = dfi['close'].pct_change(5).loc[dt]
        p = float(dfi['close'].loc[dt])
        results.append((code, name, c63, c21, c5, p))

results.sort(key=lambda x: -x[2] if not np.isnan(x[2]) else -999)

with open(r'D:\QClaw_Trading\RSRS\_rank_now_out.txt','w',encoding='utf-8') as f:
    f.write(f'Panel last date: {dt.date()}\n')
    f.write(f'{"Code":<10} {"Name":<6} {"C63":>8} {"C21":>8} {"C5":>7} {"Price":>8}\n')
    for code, name, c63, c21, c5, p in results:
        star = ' <=' if code == '588000' else ''
        c63s = f'{c63*100:>7.1f}%' if not np.isnan(c63) else '   N/A'
        c21s = f'{c21*100:>7.1f}%' if not np.isnan(c21) else '   N/A'
        c5s  = f'{c5*100:>6.1f}%'  if not np.isnan(c5)  else '  N/A'
        f.write(f'{code:<10} {name:<6} {c63s} {c21s} {c5s}  {p:.3f}{star}\n')
