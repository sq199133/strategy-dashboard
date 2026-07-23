import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'

# === 偏离度扫描 ===
files_d = sorted(glob.glob(d + r'\bt_v5_none_20260615_00182*.json'))

print("=== 偏离度参数扫描 ===")
print(f"{'偏离度':<8} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
print('-'*66)

rows = []
for fp in files_d:
    data = json.load(open(fp, encoding='utf-8'))
    s = data['stats']
    p = data['params']
    eq = data['equity']
    yy = {}
    cur, cur_yr = [], None
    for e in eq:
        yr = e['w'][:4]
        if cur_yr is None: cur_yr = yr
        if yr != cur_yr:
            if len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            cur = [e['eq']]; cur_yr = yr
        else: cur.append(e['eq'])
    if cur and len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
    rows.append((f"D{p['max_dev']}%", s['ann_ret'], s['max_dd'], s['sharpe'],
                 s.get('calmar',0), s['total_ret'], s['win_rate'],
                 yy.get('2022',0), yy.get('2026',0)))

rows.sort(key=lambda r: r[3], reverse=True)
for r in rows:
    print(f"{r[0]:<8} {r[1]:>+5.1f}% {r[2]*100:>6.1f}% {r[3]:>5.2f} {r[4]:>5.2f} {r[5]:>+6.1f}% {r[6]:>4.1f}% {r[7]:>+6.1f}% {r[8]:>+6.1f}%")

print("\n（标注←当前 为回撤>20%的风险信号）")

# === G3扫描 ===
files_g3 = sorted(glob.glob(d + r'\bt_v5_none_20260615_00?????.json'))
# Filter for recent G3 files (timestamp 0019xxxx onwards)
files_g3 = [f for f in files_g3 if '0019' in f or '0020' in f or '0021' in f or '0022' in f or '0023' in f]

if files_g3:
    print("\n=== G3过滤参数扫描 ===")
    print(f"{'MOM1W':>6} {'MOM3W':>6} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
    print('-'*75)
    g3rows = []
    for fp in files_g3:
        try:
            data = json.load(open(fp, encoding='utf-8'))
            s = data['stats']
            p = data['params']
            eq = data['equity']
            yy = {}
            cur, cur_yr = [], None
            for e in eq:
                yr = e['w'][:4]
                if cur_yr is None: cur_yr = yr
                if yr != cur_yr:
                    if len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
                    cur = [e['eq']]; cur_yr = yr
                else: cur.append(e['eq'])
            if cur and len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            g3rows.append((int(p.get('mom1w_threshold',-1)), int(p.get('mom3w_threshold',0)),
                          s['ann_ret'], s['max_dd'], s['sharpe'], s.get('calmar',0),
                          s['total_ret'], s['win_rate'], yy.get('2022',0), yy.get('2026',0)))
        except: pass
    
    g3rows.sort(key=lambda r: r[4], reverse=True)  # sort by sharpe
    for r in g3rows:
        print(f"{r[0]:>+5d}% {r[1]:>+5d}% {r[2]:>+5.1f}% {r[3]*100:>6.1f}% {r[4]:>5.2f} {r[5]:>5.2f} {r[6]:>+6.1f}% {r[7]:>4.1f}% {r[8]:>+6.1f}% {r[9]:>+6.1f}%")
