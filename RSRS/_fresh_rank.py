import sys, warnings, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_final_strategy import load_etf

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

results = []
for code, name in POOL.items():
    df = load_etf(code)
    if len(df) < 252:
        continue
    c = df['close'].values
    dt = str(df['date'].values[-1])[:10]
    c63 = c[-1]/c[-1-63] - 1
    c21 = c[-1]/c[-1-21] - 1
    c5  = c[-1]/c[-1-5]  - 1
    c10 = c[-1]/c[-1-10] - 1
    results.append((code, name, c63, c21, c5, c10, c[-1], dt))

results.sort(key=lambda x: -x[2])
with open(r'D:\QClaw_Trading\RSRS\_fresh_out.txt','w',encoding='utf-8') as f:
    f.write(f'Fresh ranking (data up to {results[0][7]}):\n')
    f.write(f'{"Code":<10}{"Name":<6}{"C63":>8}{"C21":>8}{"C5":>7}{"C10":>7}{"Px":>8}\n')
    for code, name, c63, c21, c5, c10, p, dt in results:
        star = ' <=' if code == '588000' else ''
        f.write(f'{code:<10}{name:<6}{c63*100:>7.1f}%{c21*100:>7.1f}%{c5*100:>6.1f}%{c10*100:>6.1f}%{p:>8.3f}{star}\n')
