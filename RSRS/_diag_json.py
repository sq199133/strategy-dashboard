import sys, warnings, json
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')
import numpy as np

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

with open(r'D:\QClaw_Trading\RSRS\_diag_out.txt','w',encoding='utf-8') as f:
    f.write(f'{"Code":<10}{"Name":<6}{"JSON Last":<12}{"Rows":>6}{"KC LastPx":>10}{"C63Px":>10}{"C63":>8}\n')
    
    for code, name in POOL.items():
        fp = rf'D:\QClaw_Trading\data\history\{code}.json'
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                j = json.load(fh)
            
            dates = j['dates']
            data  = j['data']
            json_last = dates[-1]
            rows = len(dates)
            
            # prices from JSON data array
            closes = [d['close'] for d in data]
            
            last_px = closes[-1]
            
            # C63: last price vs price 63 rows back
            if len(closes) >= 64:
                c63_px = closes[-1-63]
                c63_ret = (last_px / c63_px - 1) if c63_px > 0 else float('nan')
            else:
                c63_px = float('nan')
                c63_ret = float('nan')
            
            # Also get 63-day ago date for reference
            c63_date = dates[-1-63] if len(dates) >= 64 else 'N/A'
            
            f.write(f'{code:<10}{name:<6}{json_last:<12}{rows:>6}{last_px:>10.3f}{c63_px:>10.3f}{c63_ret*100:>7.1f}%\n')
        except Exception as e:
            f.write(f'{code:<10}{name:<6} ERROR: {e}\n')
