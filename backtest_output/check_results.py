import json, os, pandas as pd

d = 'D:/QClaw_Trading/backtest_output/factor_run_20260713_230732'

# Best strategy summary
best = None
best_sharpe = 0
for f in os.listdir(d):
    if f.endswith('_summary.json'):
        with open(os.path.join(d,f), encoding='utf-8') as fh:
            r = json.load(fh)
        s = r.get('sharpe', 0) or 0
        if s > best_sharpe:
            best_sharpe = s
            best = r

print('=== Best Strategy (by Sharpe) ===')
for k,v in best.items():
    print(f'  {k}: {v}')

# Low vol top5 trades
print()
print('=== Low Vol 12m top5 - Top Held ETFs ===')
prefix = '低波动12m_12m_top5'
tf = os.path.join(d, f'{prefix}_trades.csv')
if os.path.exists(tf):
    tr = pd.read_csv(tf)
    print(f'Trades: {len(tr)}')
    print(f'Held symbols: {tr["symbol"].nunique()}')
    print(f'Top 15 held ETFs:')
    vc = tr['symbol'].value_counts().head(15)
    for s, c in vc.items():
        print(f'  {s}: {c} trades')

# Multi 动量+低波 top5
print()
print('=== Multi 动量+低波 top5 - Top Held ETFs ===')
eqf = os.path.join(d, f'multi_{"动量+低波"}_top5_equity.csv')
# fix filename
for f in os.listdir(d):
    if '动量+低波' in f and 'top5' in f and 'equity' in f:
        tf2 = f.replace('_equity.csv', '_trades.csv')
        tf2 = os.path.join(d, tf2)
        if os.path.exists(tf2):
            tr2 = pd.read_csv(tf2)
            print(f'Trades: {len(tr2)}')
            print(f'Held symbols: {tr2["symbol"].nunique()}')
            print(f'Top 15 held ETFs:')
            vc2 = tr2['symbol'].value_counts().head(15)
            for s, c in vc2.items():
                print(f'  {s}: {c} trades')
        break

# Equity curve of best strategy
print()
print('=== Best Strategy Equity ===')
bf = os.path.join(d, f'{prefix}_equity.csv')
eq = pd.read_csv(bf)
print(eq.iloc[0]['date'], eq.iloc[0]['value'])
print(eq.iloc[-1]['date'], eq.iloc[-1]['value'])
print(f'Initial: {eq["value"].iloc[0]:.0f}, Final: {eq["value"].iloc[-1]:.0f}')

# Max DD analysis
eq['cummax'] = eq['value'].cummax()
eq['dd_pct'] = (eq['value'] / eq['cummax'] - 1) * 100
worst_dd = eq.loc[eq['dd_pct'].idxmin()]
print(f'Worst DD: {worst_dd["dd_pct"]:.1f}% on {worst_dd["date"]}')
