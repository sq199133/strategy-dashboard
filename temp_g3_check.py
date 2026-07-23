import json, os, sys, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    d = json.load(f)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        weeks[w] = cl
                    except:
                        pass
                return sorted(weeks.items())
            except:
                continue
    return None

for code in ['159786', '159732']:
    s = load_history(code)
    if not s:
        print(f'{code}: 无数据')
        continue
    print(f'\n{code} 最近8周:')
    for w, c in s[-8:]:
        print(f'  {w}: {c:.4f}')
    
    # 计算三周动量和本周动量
    if len(s) >= 4:
        w3_mom = s[-1][1] / s[-3][1] - 1   # 3周前
        w1_mom = s[-1][1] / s[-2][1] - 1   # 上周（本周动量）
        print(f'  三周动量: {w3_mom:+.2%}')
        print(f'  本周动量: {w1_mom:+.2%}')
        print(f'  G3过滤: 三周>0? {w3_mom>0}  本周>=-1%? {w1_mom>=-0.01}')
        if w1_mom < -0.01:
            print(f'  *** 本周动量 {w1_mom:+.2%} < -1%，G3过滤失败！***')
        if w3_mom <= 0:
            print(f'  *** 三周动量 {w3_mom:+.2%} <= 0%，G3过滤失败！***')
