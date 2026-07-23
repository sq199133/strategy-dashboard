import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files_v6 = sorted(glob.glob(d + r'\bt_v6_*.json'))

# Get all v6 results
v6_rows = []
for fp in files_v6:
    data = json.load(open(fp, encoding='utf-8'))
    s = data['stats']; p = data['params']; eq = data['equity']
    yy = {}; cur, cur_yr = [], None
    for e in eq:
        yr = e['w'][:4]
        if cur_yr is None: cur_yr = yr
        if yr != cur_yr:
            if len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            cur = [e['eq']]; cur_yr = yr
        else: cur.append(e['eq'])
    if cur and len(cur) > 1: yy[cur_yr] = (cur[-1]/cur[0]-1)*100
    
    # Build label
    lb_mode = p.get('lb_mode', 'fixed')
    if lb_mode == 'hs300':
        lb_l = f"dyn{p['lb_choppy']}/{p['lb_trend']}"
    else:
        lb_l = f"LB{p['lb']}"
    m1 = p.get('mom1w_threshold', -1)
    m3 = p.get('mom3w_threshold', 0)
    if abs(m1 + 1) > 0.01 or abs(m3) > 0.01:
        g3_l = f" G3M1W{int(m1):+d}M3W{int(m3):+d}"
    else:
        g3_l = ""
    
    v6_rows.append({
        'label': f"{lb_l}{g3_l}",
        'ann': s['ann_ret'], 'dd': s['max_dd'], 'sharpe': s['sharpe'],
        'calmar': s.get('calmar', 0), 'total': s['total_ret'], 'wr': s['win_rate'],
        'y22': yy.get('2022', 0), 'y23': yy.get('2023', 0),
        'y25': yy.get('2025', 0), 'y26': yy.get('2026', 0),
    })

v6_rows.sort(key=lambda r: r['sharpe'], reverse=True)

print(f"{'Config':<28} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2023':>7} {'2025':>7} {'2026':>8}")
print('-' * 98)
for r in v6_rows:
    print(f"{r['label']:<28} {r['ann']:>+5.1f}% {r['dd']*100:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>5.2f} {r['total']:>+6.1f}% {r['wr']:>4.1f}% {r['y22']:>+6.1f}% {r['y23']:>+6.1f}% {r['y25']:>+6.1f}% {r['y26']:>+6.1f}%")

# Add baseline from v5
print(f"\n{'Baseline':<28} {'+16.6%':>6} {'  -22.7%':>7} {' 0.83':>6} {' 0.73':>6} {'+949.6%':>8} {'41.7%':>5} {'+22.6%':>7} {' -2.2%':>7} {'+58.6%':>7} {'  -16.1%':>8}")
