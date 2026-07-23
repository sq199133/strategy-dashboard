"""Deep dive best non-gold strategies"""
import json, os, pandas as pd, numpy as np

d = 'D:/QClaw_Trading/backtest_output/factor_run_20260713_230732'

# Best non-gold strategy: 低波动3m top5 (S=4.94, gold=37%)
prefix = '低波动3m_3m_top5'
eq = pd.read_csv(os.path.join(d, f'{prefix}_equity.csv'))
eq['ym'] = pd.to_datetime(eq['date']).dt.to_period('M')
monthly = eq.groupby('ym')['value'].last()
mr = monthly.pct_change().dropna()

print("=== 低波动3m top5 - Monthly returns ===")
for ym, r in mr.items():
    print(f"  {ym}: {r*100:+.2f}%")

# Cumulative
print(f"\n  Total return: {(monthly.iloc[-1]/monthly.iloc[0]-1)*100:.1f}%")
print(f"  Avg monthly: {mr.mean()*100:.2f}%")
print(f"  Std monthly: {mr.std()*100:.2f}%")
print(f"  Monthly Sharpe: {mr.mean()/mr.std():.3f}")

# 低波动6m top10 (S=5.53, gold=47%)
print("\n\n=== 低波动6m top10 ===")
eq2 = pd.read_csv(os.path.join(d, '低波动6m_6m_top10_equity.csv'))
m2 = eq2.copy()
m2['ym'] = pd.to_datetime(m2['date']).dt.to_period('M')
m2 = m2.groupby('ym')['value'].last()
mr2 = m2.pct_change().dropna()
print(f"  Total return: {(m2.iloc[-1]/m2.iloc[0]-1)*100:.1f}%")
print(f"  Avg monthly: {mr2.mean()*100:.2f}%")
print(f"  Sharpe: {mr2.mean()/mr2.std()*np.sqrt(12):.3f}")

# What about gold-only performance?
print("\n\n=== Gold ETF-only strategy (buy 518880 and hold) ===")
# Load gold data
with open('D:/QClaw_Trading/data/history/518880.json', encoding='utf-8') as f:
    gd = json.load(f)
gdf = pd.DataFrame(gd['records'])
gdf['date'] = pd.to_datetime(gdf['date'])
gdf = gdf.sort_values('date')
gdf = gdf[gdf['date'] >= '2021-01-04']
gdf = gdf[gdf['date'] <= '2026-07-13']
print(f"  Start: {gdf.iloc[0]['date'].date()} close={gdf.iloc[0]['close']}")
print(f"  End: {gdf.iloc[-1]['date'].date()} close={gdf.iloc[-1]['close']}")
print(f"  Buy-Hold return: {(gdf.iloc[-1]['close']/gdf.iloc[0]['close']-1)*100:.1f}%")
gr = gdf['close'].pct_change().dropna()
print(f"  Ann Sharpe: {gr.mean()/gr.std()*np.sqrt(252):.3f}")

# What non-gold ETFs show up in low vol 6m top10?
print("\n\n=== 低波动6m top10 - non-gold positions ===")
tr = pd.read_csv(os.path.join(d, '低波动6m_6m_top10_trades.csv'))
tr['sym'] = tr['symbol'].astype(str)
ng = tr[~tr['sym'].str.startswith('518')]
print(f"  Non-gold positions: {ng['sym'].nunique()} symbols")
for s, g in ng.groupby('sym'):
    print(f"  {s}: {len(g)} trades, pnl={g['pnl'].sum():.0f}")
