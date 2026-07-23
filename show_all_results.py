import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
# MA results
files_ma = sorted(glob.glob(d + r'\bt_v5_none_20260615_0013*.json'))

print("=== 【A组】MA参数扫描 ===")
print(f"{'MA':<12} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
print('-'*66)
rows_ma = [
    ('MA5/21', 16.6, -22.7, 0.83, 0.73, 949.6, 41.7, +22.6, -16.1),
]
for fp in files_ma:
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
    l = f"MA{p['ma_s']}/{p['ma_l']}"
    rows_ma.append((l, s['ann_ret'], s['max_dd'], s['sharpe'], s.get('calmar',0),
                    s['total_ret'], s['win_rate'], yy.get('2022',0), yy.get('2026',0)))

rows_ma.sort(key=lambda r: r[3], reverse=True)
for r in rows_ma:
    print(f"{r[0]:<12} {r[1]:>+5.1f}% {r[2]*100:>6.1f}% {r[3]:>5.2f} {r[4]:>5.2f} {r[5]:>+6.1f}% {r[6]:>4.1f}% {r[7]:>+6.1f}% {r[8]:>+6.1f}%")

print("\n=== 【B组】动态LB ===")
files_dyn = sorted(glob.glob(d + r'\bt_v6_*.json'))
print(f"{'Config':<12} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
print('-'*66)
rows_dyn = []
for fp in files_dyn:
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
    
    lb_mode = p.get('lb_mode', 'fixed')
    if lb_mode == 'hs300':
        l = f"dyn{p['lb_choppy']}/{p['lb_trend']}"
    else:
        l = f"LB{p['lb']}"
    rows_dyn.append((l, s['ann_ret'], s['max_dd'], s['sharpe'], s.get('calmar',0),
                     s['total_ret'], s['win_rate'], yy.get('2022',0), yy.get('2026',0)))

rows_dyn.sort(key=lambda r: r[3], reverse=True)
for r in rows_dyn:
    print(f"{r[0]:<12} {r[1]:>+5.1f}% {r[2]*100:>6.1f}% {r[3]:>5.2f} {r[4]:>5.2f} {r[5]:>+6.1f}% {r[6]:>4.1f}% {r[7]:>+6.1f}% {r[8]:>+6.1f}%")

# Add baseline
print(f"{'LB3(基线)':<12} {16.6:>+5.1f}% {-22.7:>6.1f}% {0.83:>5.2f} {0.73:>5.2f} {949.6:>+6.1f}% {41.7:>4.1f}% {+22.6:>+6.1f}% {-16.1:>+6.1f}%")
