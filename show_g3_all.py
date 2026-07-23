import glob, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files = sorted(glob.glob(d + r'\bt_v5_none_20260615_*.json'))

print(f"Total files: {len(files)}")

# Find G3 parameters files (those with mom1w_threshold in params)
rows = []
for f in files:
    data = json.load(open(f, encoding='utf-8'))
    p = data['params']
    if 'mom1w_threshold' in p or 'mom3w_threshold' in p:
        s = data['stats']
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
        
        m1 = int(p.get('mom1w_threshold', -1))
        m3 = int(p.get('mom3w_threshold', 0))
        rows.append((m1, m3, s['ann_ret'], s['max_dd'], s['sharpe'],
                     s.get('calmar',0), s['total_ret'], s['win_rate'],
                     yy.get('2022',0), yy.get('2026',0)))

print(f"G3 files found: {len(rows)}")

# Sort by sharpe descending
rows.sort(key=lambda r: r[4], reverse=True)

print(f"{'M1W':>5} {'M3W':>5} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
print('-' * 68)
for r in rows:
    print(f"{r[0]:>+4d}% {r[1]:>+4d}% {r[2]:>+5.1f}% {r[3]*100:>6.1f}% {r[4]:>5.2f} {r[5]:>5.2f} {r[6]:>+6.1f}% {r[7]:>4.1f}% {r[8]:>+6.1f}% {r[9]:>+6.1f}%")
