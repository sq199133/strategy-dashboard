import sys, warnings, json
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

POOL = {'510050':'SH50','510300':'HS300','510500':'ZZ500','512100':'ZZ1000',
        '159915':'CYB','588000':'KC50','513500':'SP500','513100':'NSDQ',
        '518880':'GOLD','162411':'OIL','515080':'ZSHL'}

with open(r'D:\QClaw_Trading\RSRS\_diag_dates_out.txt','w',encoding='utf-8') as f:
    f.write(f'{"Code":<10}{"Name":<6}{"JSON Last":<12}{"Update":<12}{"Rows":>6}{"KC LastPx":>10}\n')
    
    for code, name in POOL.items():
        fp = rf'D:\QClaw_Trading\data\history\{code}.json'
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                j = json.load(fh)
            recs = j['records']
            last_rec = recs[-1]
            last_date = last_rec['date']
            last_px = last_rec['close']
            rows = len(recs)
            upd = j.get('update', 'N/A')
            f.write(f'{code:<10}{name:<6}{last_date:<12}{upd:<12}{rows:>6}{last_px:>10.3f}\n')
        except Exception as e:
            f.write(f'{code:<10}{name:<6} ERROR: {e}\n')
