import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files = sorted(glob.glob(d + r'\bt_v6_*.json'))

all_results = []
for fp in files:
    data = json.load(open(fp, encoding='utf-8'))
    s = data['stats']
    params = data['params']
    
    # yearly from equity
    eq = data['equity']
    yy = {}
    cur, cur_yr = [], None
    for e in eq:
        yr = e['w'][:4]
        if cur_yr is None: cur_yr = yr
        if yr != cur_yr:
            if len(cur) > 1:
                yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            cur = [e['eq']]; cur_yr = yr
        else:
            cur.append(e['eq'])
    if cur and len(cur) > 1:
        yy[cur_yr] = (cur[-1]/cur[0]-1)*100
    
    lb_mode = params.get('lb_mode', 'fixed')
    lb = params.get('lb', 3)
    if lb_mode == 'hs300':
        lb_label = f"dyn{params.get('lb_choppy',2)}/{params.get('lb_trend',3)}"
    else:
        lb_label = f"LB{lb}"
    
    all_results.append({
        'label': lb_label, 'ann': s['ann_ret'], 'dd': s['max_dd'],
        'sharpe': s['sharpe'], 'calmar': s.get('calmar', 0),
        'total': s['total_ret'], 'wr': s['win_rate'],
        'nb': s['n_buys'], 'ns': s['n_sells'],
        'y26': yy.get('2026', 0), 'y22': yy.get('2022', 0),
        'y23': yy.get('2023', 0), 'y25': yy.get('2025', 0),
    })

all_results.sort(key=lambda r: r['sharpe'], reverse=True)

print(f"{'Config':<12} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'Trades':>6} {'2022':>7} {'2023':>7} {'2025':>7} {'2026':>7}")
print('-' * 88)
for r in all_results:
    print(f"{r['label']:<12} {r['ann']:>+5.1f}% {r['dd']*100:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>5.2f} {r['total']:>+6.1f}% {r['wr']:>4.1f}% {r['nb']+r['ns']:>5d}  {r['y22']:>+6.1f}% {r['y23']:>+6.1f}% {r['y25']:>+6.1f}% {r['y26']:>+6.1f}%")

# Also add baseline from earlier
print("\n=== Baseline (from backtest_v5 earlier) ===")
print(f"{'LB3':<12} {16.6:>+5.1f}% {-22.7:>6.1f}% {0.83:>5.2f} {'0.73':>5} {949.6:>+6.1f}% {41.7:>4.1f}%")
