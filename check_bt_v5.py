import json, glob, os

files = sorted(glob.glob('D:/QClaw_Trading/backtest_results/bt_v5_*.json'))
if not files:
    print("No files found!")
else:
    for fp in files[-5:]:
        with open(fp) as f:
            d = json.load(f)
        s = d['stats']
        label = d.get('label', '?')
        md = s['max_dd'] * 100 if abs(s['max_dd']) < 1 else s['max_dd']
        print(f"{os.path.basename(fp):60s} | {label:40s} | ann={s['ann_ret']:+.1f}% dd={abs(md):.1f}% S={s['sharpe']:.2f}")
