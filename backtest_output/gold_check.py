"""Exclude gold ETFs and rerun key strategies"""
import json, os, pandas as pd, numpy as np

d = 'D:/QClaw_Trading/backtest_output/factor_run_20260713_230732'
data_dir = 'D:/QClaw_Trading/data/history/'

# All summary results sorted by Sharpe
summaries = []
for f in os.listdir(d):
    if f.endswith('_summary.json'):
        with open(os.path.join(d,f), encoding='utf-8') as fh:
            r = json.load(fh)
        r['file_prefix'] = f.replace('_summary.json', '')
        summaries.append(r)

summaries.sort(key=lambda x: x.get('sharpe', 0) or 0, reverse=True)

print("=== Top 15 by Sharpe (checking gold dominance) ===")
for r in summaries[:15]:
    tf = os.path.join(d, f"{r['file_prefix']}_trades.csv")
    if os.path.exists(tf):
        tr = pd.read_csv(tf)
        tr['sym'] = tr['symbol'].astype(str)
        gold_mask = tr['sym'].str.startswith('518')
        gold_pnl = tr.loc[gold_mask, 'pnl'].sum()
        total_pnl = tr['pnl'].sum()
        gpct = gold_pnl / total_pnl * 100 if total_pnl != 0 else 0
        print(f"  S={r['sharpe']:.2f} R={r['annual_return_pct']:.1f}% {r['factor_name']:20s} {r['param_label']:10s} T{r['top_k']:2d}  gold_pnl={gpct:.0f}% trades={len(tr):4d}")

# Check best non-gold strategies
print()
print("=== Strategies with <50% gold contribution ===")
for r in summaries:
    tf = os.path.join(d, f"{r['file_prefix']}_trades.csv")
    if not os.path.exists(tf):
        continue
    tr = pd.read_csv(tf)
    tr['sym'] = tr['symbol'].astype(str)
    gold_mask = tr['sym'].str.startswith('518')
    gold_pnl = tr.loc[gold_mask, 'pnl'].sum()
    total_pnl = tr['pnl'].sum()
    gpct = gold_pnl / max(total_pnl, 1) * 100
    if gpct < 50 and r.get('sharpe', 0) is not None and r['sharpe'] > 0.5:
        print(f"  S={r['sharpe']:.2f} R={r['annual_return_pct']:.1f}% {r['factor_name']:20s} {r['param_label']:10s} T{r['top_k']:2d}  gold={gpct:.0f}% trades={len(tr):4d}")

# Non-gold low vol: what does top20 look like?
print()
print("=== Low Vol 12m top20 - non-gold only analysis ===")
prefix = '低波动12m_12m_top20'
tf = os.path.join(d, f'{prefix}_trades.csv')
tr = pd.read_csv(tf)
tr['sym'] = tr['symbol'].astype(str)
ng = tr[~tr['sym'].str.startswith('518')]
print(f"Non-gold trades: {len(ng)} / {len(tr)}")
print(f"Non-gold pnl: {ng['pnl'].sum():.0f}")
print(f"Top non-gold held:")
for s, g in ng.groupby('sym'):
    print(f"  {s}: {len(g)} trades, pnl={g['pnl'].sum():.0f}")
