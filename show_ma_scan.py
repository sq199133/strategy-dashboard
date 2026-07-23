import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files = sorted(glob.glob(d + r'\bt_v5_none_20260615_0013*.json'))

configs = []
for fp in files:
    data = json.load(open(fp, encoding='utf-8'))
    s = data['stats']
    eq = data['equity']
    yy = {}
    cur, cur_yr = [], None
    for e in eq:
        yr = e['w'][:4]
        if cur_yr is None:
            cur_yr = yr
        if yr != cur_yr:
            if len(cur) > 1:
                yy[cur_yr] = (cur[-1]/cur[0]-1)*100
            cur = [e['eq']]; cur_yr = yr
        else:
            cur.append(e['eq'])
    if cur and len(cur) > 1:
        yy[cur_yr] = (cur[-1]/cur[0]-1)*100
    
    params = data['params']
    label = f"MA{params['ma_s']}/{params['ma_l']} LB{params['lb']} D{params['max_dev']} H{params['top_n']}"
    configs.append({
        'label': label, 'ann': s['ann_ret'], 'dd': s['max_dd'],
        'sharpe': s['sharpe'], 'calmar': s.get('calmar', 0),
        'total': s['total_ret'], 'wr': s['win_rate'],
        'y26': yy.get('2026', 0), 'y22': yy.get('2022', 0),
    })

# Add baseline
configs.append({
    'label': 'MA5/21 LB3 D10 H2 (baseline)',
    'ann': 16.6, 'dd': -0.227, 'sharpe': 0.83, 'calmar': 0.73,
    'total': 949.6, 'wr': 41.7, 'y26': -16.1, 'y22': 22.6,
})

configs.sort(key=lambda r: r['sharpe'], reverse=True)

print(f"{'Param':<36} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7}")
print('-' * 88)
for r in configs:
    print(f"{r['label']:<36} {r['ann']:>+5.1f}% {r['dd']*100:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>5.2f} {r['total']:>+6.1f}% {r['wr']:>4.1f}% {r['y22']:>+6.1f}% {r['y26']:>+6.1f}%")
