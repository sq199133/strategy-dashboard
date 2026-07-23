import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.chdir(r'D:\Qclaw_Trading')
sys.path.insert(0, '.')
import weekly_scan_v4 as ws

etfs = ws.load_pool()
pool = {e['code']: e.get('name','') for e in etfs}

codes = ['517850','159572','159761','562800','159687','588220']
print('G3过滤检查（M3W>=0% AND M1W>=-1%）')
print()
for code in codes:
    name = pool.get(code,'')
    wk = ws.load_weekly_file(code)
    if wk is None: continue
    wk = ws.filter_completed_weeks(wk)
    ni = ws.calc(wk)
    if ni is None: continue
    ind = ni[-1]
    
    mom1w = wk[-1]['close'] / wk[-2]['close'] - 1 if len(wk) >= 2 else None
    mom3w = wk[-1]['close'] / wk[-3]['close'] - 1 if len(wk) >= 3 else None
    
    g3_pass = True
    reasons = []
    if mom1w is not None and mom1w < -0.01:
        g3_pass = False
        reasons.append(f'M1W={mom1w:+.2%} < -1%')
    if mom3w is not None and mom3w < 0:
        g3_pass = False
        reasons.append(f'M3W={mom3w:+.2%} < 0%')
    
    score = ind.get('score', 0)
    g3_icon = 'PASS' if g3_pass else 'FAIL'
    
    print(f'{code} {name}')
    print(f'  M1W={mom1w:+.2%}  M3W={mom3w:+.2%}')
    print(f'  G3: {g3_icon}  score={score:+.2%}')
    if reasons:
        print(f'  原因: {", ".join(reasons)}')
    print()
