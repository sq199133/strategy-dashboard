import json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = r'D:\Qclaw_Trading\backtest_results'
files_d = sorted(glob.glob(d + r'\bt_v5_none_20260615_0018*.json'))
# exclude G3 files (timestamps with 00184, 00185)
files_d = [f for f in files_d if '00184' not in f and '00185' not in f]

print("=== 偏离度全表 ===")
for f in files_d:
    data = json.load(open(f, encoding='utf-8'))
    s = data['stats']
    p = data['params']
    fshort = f[-32:]
    print(f'{fshort} D{p["max_dev"]}% ann={s["ann_ret"]:+.1f}% dd={s["max_dd"]*100:.1f}% sharpe={s["sharpe"]:.2f} calmar={s.get("calmar",0):.2f}')

# G3 - all 20 combos
print("\n=== G3全表 (20组按夏普排序) ===")
g3_files = sorted(glob.glob(d + r'\bt_v5_none_20260615_00?????.json'))
g3_files = [f for f in g3_files if '0018' in f[-16:-13] or '0019' in f[-16:-13] or '0020' in f[-16:-13] or '0021' in f[-16:-13] or '0022' in f[-16:-13] or '0023' in f[-16:-13]]
g3_files = [f for f in g3_files if not('00182' in f[-17:-14] or '00183' in f[-17:-14])]
# Only the ones after 001843 (when G3 scan started)
g3_files = [f for f in g3_files if int(f.split('_')[-1].split('.')[0]) >= 1843]

rows = []
for f in g3_files:
    try:
        data = json.load(open(f, encoding='utf-8'))
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
        m1 = int(p.get('mom1w_threshold',-1))
        m3 = int(p.get('mom3w_threshold',0))
        rows.append((m1, m3, s['ann_ret'], s['max_dd'], s['sharpe'], s.get('calmar',0),
                     s['total_ret'], s['win_rate'], yy.get('2022',0), yy.get('2026',0)))
    except Exception as ex:
        pass

rows.sort(key=lambda r: r[4], reverse=True)
print(f"{'M1W':>5} {'M3W':>5} {'Ann':>6} {'DD':>7} {'Sharpe':>6} {'Calmar':>6} {'Total':>8} {'Win%':>5} {'2022':>7} {'2026':>7} {'Trades':>6}")
print('-' * 68)
for r in rows:
    print(f"{r[0]:>+4d}% {r[1]:>+4d}% {r[2]:>+5.1f}% {r[3]*100:>6.1f}% {r[4]:>5.2f} {r[5]:>5.2f} {r[6]:>+6.1f}% {r[7]:>4.1f}% {r[8]:>+6.1f}% {r[9]:>+6.1f}%")
