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
                        if w not in weeks or ds > weeks[w][0]:
                            weeks[w] = (ds, cl)
                    except:
                        pass
                sorted_weeks = sorted(weeks.items())
                return sorted_weeks
            except:
                continue
    return None

for code in ['159786', '159732']:
    print(f'\n{"="*60}')
    print(f'  {code}')
    print(f'{"="*60}')
    s = load_history(code)
    if not s:
        print('  无数据')
        continue
    print(f'  数据周数: {len(s)}')
    print(f'  最近10周:')
    for w, (ds, cl) in s[-10:]:
        print(f'    {w} ({ds}): {cl:.4f}')
    
    cs = [cl for w, (ds, cl) in s]
    n = len(cs)
    
    if n >= 4:
        w3 = cs[-1] / cs[-3] - 1   # 2周前
        w1 = cs[-1] / cs[-2] - 1   # 上周
        print(f'\n  三周动量(LB=3): {w3:+.2%}')
        print(f'  本周动量:     {w1:+.2%}')
        print(f'  G3: 三周>0? {w3>0}  本周>=-1%? {w1>=-0.01}')
        if w1 < -0.01:
            print(f'  *** 本周动量 {w1:+.2%} < -1%，G3失败！***')
        if w3 <= 0:
            print(f'  *** 三周动量 {w3:+.2%} <= 0%，G3失败！***')
        if w3 > 0 and w1 >= -0.01:
            print(f'  G3通过')
    else:
        print(f'\n  数据不足{n}周，无法计算动量')
