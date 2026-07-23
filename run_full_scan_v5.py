#!/usr/bin/env python3
"""Full parameter scan with fixed price logic (sig_week close) - v2"""
import subprocess, os, json, glob, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'D:\Qclaw_Trading'
os.chdir(BASE)

def parse_yearly(text):
    """Parse yearly section from printed output"""
    year_data = {}
    in_years = False
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('Year') and 'Ret' in line:
            in_years = True
            continue
        if not in_years or not line:
            continue
        if line.startswith('Saved') or line.startswith('==='):
            break
        if line.startswith('---'):
            continue
        if line[0].isdigit():
            parts = line.split()
            if len(parts) >= 4:
                try:
                    ret_s = parts[1].replace('%','').strip()
                    dd_s = parts[2].replace('%','').strip()
                    year_data[int(parts[0])] = {'ret': float(ret_s), 'dd': float(dd_s)}
                except:
                    pass
    return year_data

def run(label, args):
    cmd = f'python backtest_v5_qual_sizer.py {args} 2>&1'
    print(f'  ⟳ {label}...', end=' ', flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    out = r.stdout
    
    files = sorted(glob.glob(os.path.join(BASE, 'backtest_results', 'bt_v5_*.json')), key=os.path.getmtime)
    if not files:
        print('NO_FILE')
        return None
    with open(files[-1]) as f:
        d = json.load(f)
    
    s = d['stats']
    yearly = parse_yearly(out)
    yr26 = yearly.get(2026, {'ret': 0, 'dd': 0})
    
    return {
        'label': d['label'],
        'total': s['total_ret'],
        'annual': s['ann_ret'],
        'maxdd': s['max_dd'] * 100,
        'sharpe': s['sharpe'],
        'win': s['win_rate'] / 100,
        'y2026': yr26['ret'],
        'y2026dd': yr26['dd'],
    }

def show_results(header, keys, data_list, fmt):
    """Print formatted results table"""
    print(f'\n\n══════════ {header} ══════════')
    print(fmt['header'])
    print('-' * fmt['width'])
    for d in data_list:
        print(fmt['row'].format(*[d[k] if isinstance(d[k], str) else d[k] for k in keys]))

# ═══════════════════════════════════════════════
# 1. G3 阈值扫描
# ═══════════════════════════════════════════════
g3_fmt = {
    'header': f"{'M1W':>6s} {'M3W':>6s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}",
    'width': 68, 'row': '{0:>+5d}% {1:>+5d}%  {2:>+5.1f}%  {3:.2f}  {4:>5.1f}%  {5:>+6.1f}%  {6:.0%}  {7:>+5.1f}%  {8:>5.1f}%'
}
g3_results = []
for m1 in [-1, 0, 1, 2]:
    for m3 in [-2, -1, 0]:
        r = run(f'G3 M1W={m1} M3W={m3}', f'--mom1w-threshold {m1} --mom3w-threshold {m3} --output g3_{m1}_{m3}')
        if r:
            g3_results.append(r)
            print(f'{m1:>+5d}% {m3:>+5d}%  {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')
        else:
            print(f'  FAIL')

# ═══════════════════════════════════════════════
# 2. 复合评分权重扫描
# ═══════════════════════════════════════════════
sc_fmt = {
    'header': f"{'w1':>4s} {'w3':>4s} {'w8':>4s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}",
    'width': 71, 'row': '{0:>3d}% {1:>3d}% {2:>3d}%  {3:>+5.1f}%  {4:.2f}  {5:>5.1f}%  {6:>+6.1f}%  {7:.0%}  {8:>+5.1f}%  {9:>5.1f}%'
}
sc_results = []
weights = [
    (0.0, 1.0), (0.2, 0.5), (0.3, 0.5), (0.3, 0.6),
    (0.4, 0.4), (0.4, 0.5), (0.5, 0.3), (0.5, 0.4),
    (0.6, 0.2), (0.6, 0.3), (0.7, 0.2), (0.7, 0.1),
]
for w1, w3 in weights:
    w8 = round(1.0 - w1 - w3, 1)
    r = run(f'SC {int(w1*100)}/{int(w3*100)}/{int(w8*100)}',
            f'--score-mode composite --score-w1 {w1} --score-w3 {w3} --output sc_{int(w1*100)}_{int(w3*100)}_{int(w8*100)}')
    if r:
        sc_results.append(r)
        print(f'{int(w1*100):>3d}% {int(w3*100):>3d}% {int(w8*100):>3d}%  {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')

# ═══════════════════════════════════════════════
# 3. LB 扫描
# ═══════════════════════════════════════════════
lb_fmt = {
    'header': f"{'LB':>4s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}",
    'width': 60, 'row': '  {0:>2d}  {1:>+5.1f}%  {2:.2f}  {3:>5.1f}%  {4:>+6.1f}%  {5:.0%}  {6:>+5.1f}%  {7:>5.1f}%'
}
lb_results = []
for lb in [2, 3, 4, 5, 6]:
    r = run(f'LB={lb}', f'--lb {lb} --output lb{lb}')
    if r:
        lb_results.append(r)
        print(f'  {lb:>2d}  {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')

# ═══════════════════════════════════════════════
# 4. 偏离度扫描
# ═══════════════════════════════════════════════
dev_fmt = lb_fmt.copy()
dev_fmt['header'] = f"{'Dev':>4s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}"
dev_results = []
for dev in [5, 10, 15, 20]:
    r = run(f'D={dev}%', f'--max-dev {dev} --output d{dev}')
    if r:
        dev_results.append(r)
        print(f'{dev:>3d}%  {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')

# ═══════════════════════════════════════════════
# 5. 持仓数量扫描
# ═══════════════════════════════════════════════
h_fmt = lb_fmt.copy()
h_fmt['header'] = f"{'H':>3s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}"
h_results = []
for h in [1, 2, 3, 4]:
    r = run(f'H={h}', f'--top-n {h} --output h{h}')
    if r:
        h_results.append(r)
        print(f'{h:>2d}   {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')

# ═══════════════════════════════════════════════
# 6. MA 扫描
# ═══════════════════════════════════════════════
ma_fmt = {
    'header': f"{'MA_s':>5s} {'MA_l':>5s} {'年化':>6s} {'夏普':>6s} {'回撤':>7s} {'总收益':>8s} {'胜率':>6s} {'2026':>7s} {'2026DD':>7s}",
    'width': 65, 'row': '{0:>3d}  {1:>3d}   {2:>+5.1f}%  {3:.2f}  {4:>5.1f}%  {5:>+6.1f}%  {6:.0%}  {7:>+5.1f}%  {8:>5.1f}%'
}
ma_pairs = [(5, 21), (10, 21), (20, 40), (10, 40), (20, 60)]
ma_results = []
for ms, ml in ma_pairs:
    r = run(f'MA{ms}/{ml}', f'--ma-s {ms} --ma-l {ml} --output ma{ms}_{ml}')
    if r:
        ma_results.append(r)
        print(f'{ms:>3d}  {ml:>3d}   {r["annual"]:>+5.1f}%  {r["sharpe"]:.2f}  {r["maxdd"]:>5.1f}%  {r["total"]:>+6.1f}%  {r["win"]:.0%}  {r["y2026"]:>+5.1f}%  {r["y2026dd"]:>5.1f}%')

print(f'\n\n{"="*55}')
print('         全部扫描完成')
print(f'{"="*55}')

# ═══════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════
def best_of(lst, key, label):
    if not lst:
        return None
    best = max(lst, key=lambda x: x[key])
    return f'  🏆 {label}: 年化{best["annual"]:+.1f}%  夏普{best["sharpe"]:.2f}  回撤{best["maxdd"]:.1f}%  2026:{best["y2026"]:+.1f}%'

print('\n\n══════════ 各维度最优（按夏普） ══════════')
if g3_results: print(f'\nG3阈值:')
if g3_results: print(best_of(g3_results, 'sharpe', ''))
if sc_results: print(f'\n复合评分权重:')
if sc_results: print(best_of(sc_results, 'sharpe', ''))
if lb_results: print(f'\nLB:')
if lb_results: print(best_of(lb_results, 'sharpe', ''))
if dev_results: print(f'\n偏离度:')
if dev_results: print(best_of(dev_results, 'sharpe', ''))
if h_results: print(f'\n持仓数:')
if h_results: print(best_of(h_results, 'sharpe', ''))
if ma_results: print(f'\nMA参数:')
if ma_results: print(best_of(ma_results, 'sharpe', ''))
