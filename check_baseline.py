import json, glob, os

files = glob.glob('D:/Qclaw_Trading/backtest_results/bt_v5_none*.json')
for f in sorted(files):
    base = os.path.basename(f)
    d = json.load(open(f))
    s = d['stats']
    md = s['max_dd'] * 100 if abs(s['max_dd']) < 1 else s['max_dd']
    print(f"{base:70s} ann={s['ann_ret']:+.1f}%  dd={abs(md):.1f}%  S={s['sharpe']:.2f}  C={s['calmar']:.2f}  loaded={d['label']}")
