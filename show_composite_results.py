import json, glob, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files = sorted(glob.glob(d + r'\bt_v5_none_20260615_0031*.json')) + sorted(glob.glob(d + r'\bt_v5_none_20260615_0030*.json'))

rows = []
for fp in files:
    data = json.load(open(fp, encoding='utf-8'))
    s = data['stats']; p = data['params']; eq = data['equity']
    # yearly calcs
    yy = {}; cur, cur_yr = [], None
    for e in eq:
        yr = e['w'][:4]
        if cur_yr is None: cur_yr = yr
        if yr != cur_yr:
            if len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            cur = [e['eq']]; cur_yr = yr
        else: cur.append(e['eq'])
    if cur and len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
    
    mode = p.get('score_mode','lb3')
    if mode == 'composite':
        w1 = int(p.get('score_w1',0.3)*100)
        w3 = int(p.get('score_w3',0.5)*100)
        w8 = 100-w1-w3
        label = f"SC{w1}-{w3}-{w8}"
        if p.get('no_ma_filter', False):
            label += " noMA"
    elif mode == 'lb3':
        if p.get('no_ma_filter', False):
            label = "noMA"
        else:
            sc_w1 = p.get('score_w1', 0.3)
            sc_w3 = p.get('score_w3', 0.5)
            label = "Baseline"
    # dedup: skip test 1 (003046) since SC33 comes later
    if '003046' in fp:
        continue
    if '003022' in fp:
        continue
    
    rows.append((label, s['ann_ret'], s['max_dd'], s['sharpe'], s.get('calmar',0),
                 s['total_ret'], s['win_rate'],
                 yy.get('2022',0), yy.get('2023',0), yy.get('2025',0), yy.get('2026',0)))

seen = set()
unique = []
for r in rows:
    key_r = r[0]
    if key_r not in seen:
        seen.add(key_r)
        unique.append(r)
rows = sorted(unique, key=lambda r: r[3], reverse=True)

print(f"{'Config':<20} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2023':>7} {'2025':>7} {'2026':>8}")
print('-' * 90)
for r in rows:
    print(f"{r[0]:<20} {r[1]:>+5.1f}% {r[2]*100:>6.1f}% {r[3]:>5.2f} {r[4]:>5.2f} {r[5]:>+6.1f}% {r[6]:>4.1f}% {r[7]:>+6.1f}% {r[8]:>+6.1f}% {r[9]:>+6.1f}% {r[10]:>+6.1f}%")
