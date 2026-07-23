import sys, warnings, json, numpy as np
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

results = []

for code, name in POOL.items():
    fp = rf'D:\QClaw_Trading\data\history\{code}.json'
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            j = json.load(fh)
        recs = j['records']
        closes = [r['close'] for r in recs]
        dates  = [r['date']  for r in recs]
        
        last_idx = len(closes) - 1
        last_date = dates[last_idx]
        last_px   = closes[last_idx]
        
        # C63: need at least 64 rows
        if len(closes) >= 64:
            c63_ret = closes[last_idx] / closes[last_idx - 63] - 1
            c63_px  = closes[last_idx - 63]
            c63_dt  = dates[last_idx - 63]
        else:
            c63_ret = float('nan')
            c63_px  = float('nan')
            c63_dt  = 'N/A'
        
        # C21
        if len(closes) >= 22:
            c21_ret = closes[last_idx] / closes[last_idx - 21] - 1
        else:
            c21_ret = float('nan')
        
        # C5
        if len(closes) >= 6:
            c5_ret = closes[last_idx] / closes[last_idx - 5] - 1
        else:
            c5_ret = float('nan')
        
        results.append((code, name, c63_ret, c21_ret, c5_ret, c63_dt, last_date, last_px))
    except Exception as e:
        results.append((code, name, float('nan'), float('nan'), float('nan'), 'ERR', 'ERR', 0))

# Sort by C63
results.sort(key=lambda x: -x[2] if not np.isnan(x[2]) else -999)

with open(r'D:\QClaw_Trading\RSRS\_fresh_rank2_out.txt','w',encoding='utf-8') as f:
    f.write('C63 Momentum Ranking (each ETF uses its own latest available date)\n')
    f.write(f'{"Rank":<5}{"Code":<10}{"Name":<6}{"C63":>8}{"C21":>8}{"C5":>7}{"LastPx":>8}{"DataDt":<12}{"C63Start":<12}\n')
    for rank, (code, name, c63, c21, c5, last_dt, data_dt, last_px) in enumerate(results, 1):
        star = ' <=' if code == '588000' else ''
        c63s = f'{c63*100:>7.1f}%' if not np.isnan(c63) else '   N/A'
        c21s = f'{c21*100:>7.1f}%' if not np.isnan(c21) else '   N/A'
        c5s  = f'{c5*100:>6.1f}%'  if not np.isnan(c5)  else '  N/A'
        f.write(f'{rank:<5}{code:<10}{name:<6}{c63s}{c21s}{c5s} {last_px:>7.3f} {data_dt:<12}{c63_dt:<12}{star}\n')
