import json, os, pandas as pd, numpy as np

d = 'D:/QClaw_Trading/backtest_output/long_run_20260714_225010'
dd = 'D:/QClaw_Trading/data/history/'

# Gold 2015~2026 full period
gf = os.path.join(dd, '518880.json')
with open(gf, encoding='utf-8') as f:
    gd = json.load(f)
gdf = pd.DataFrame(gd['records'])
gdf['date'] = pd.to_datetime(gdf['date'])
gdf = gdf.sort_values('date')
gdf = gdf[gdf['date'] >= '2015-01-01']
gdf = gdf[gdf['date'] <= '2026-07-14']
print(f"GOLD 518880: {gdf.iloc[0]['date'].date()} ~ {gdf.iloc[-1]['date'].date()}")
print(f"  {gdf.iloc[0]['close']:.3f} -> {gdf.iloc[-1]['close']:.3f}")
print(f"  Return: {(gdf.iloc[-1]['close']/gdf.iloc[0]['close']-1)*100:.1f}%")
gr = gdf['close'].pct_change().dropna()
print(f"  Ann Sharpe: {gr.mean()/gr.std()*np.sqrt(252):.3f}")

# Low vol 12m top5 - gold contribution
print("\n=== 低波动12m top5 - Gold contribution ===")
prefix1 = '低波动12m_12m_top5'
tr1 = pd.read_csv(os.path.join(d, f'{prefix1}_trades.csv'))
tr1['sym'] = tr1['symbol'].astype(str)
gm = tr1['sym'].str.startswith('518')
gp1 = tr1.loc[gm, 'pnl'].sum()
tp1 = tr1['pnl'].sum()
print(f"  Trades: {len(tr1)}, Unique symbols: {tr1['sym'].nunique()}")
print(f"  Gold trades: {gm.sum()} / {len(tr1)}")
print(f"  Gold pnl: {gp1:.0f} / {tp1:.0f} = {gp1/tp1*100:.0f}%")
gold_syms = tr1.loc[gm, 'sym'].unique()
print(f"  Gold ETFs held: {list(gold_syms)}")
vc = tr1['sym'].value_counts().head(20)
print(f"  Top held:")
for s, c in vc.items():
    s_pnl = tr1[tr1['sym']==s]['pnl'].sum()
    print(f"    {s}: {c} trades, pnl={s_pnl:.0f}")

# Low vol 6m top5 - gold
print("\n=== 低波动6m top5 - Gold contribution ===")
prefix2 = '低波动6m_6m_top5'
tr2 = pd.read_csv(os.path.join(d, f'{prefix2}_trades.csv'))
tr2['sym'] = tr2['symbol'].astype(str)
gm2 = tr2['sym'].str.startswith('518')
gp2 = tr2.loc[gm2, 'pnl'].sum()
tp2 = tr2['pnl'].sum()
print(f"  Gold pnl: {gp2:.0f} / {tp2:.0f} = {gp2/tp2*100:.0f}%")

# Low vol 3m top5 - gold
print("\n=== 低波动3m top5 - Gold contribution ===")
prefix3 = '低波动3m_3m_top5'
tr3 = pd.read_csv(os.path.join(d, f'{prefix3}_trades.csv'))
tr3['sym'] = tr3['symbol'].astype(str)
gm3 = tr3['sym'].str.startswith('518')
gp3 = tr3.loc[gm3, 'pnl'].sum()
tp3 = tr3['pnl'].sum()
print(f"  Gold pnl: {gp3:.0f} / {tp3:.0f} = {gp3/tp3*100:.0f}%")
print(f"  Unique non-gold held: {tr3[~gm3]['sym'].nunique()}")

# Check when each gold ETF first entered its history
print("\n=== Gold ETF start dates ===")
for code in gold_syms:
    with open(os.path.join(dd, f'{code}.json'), encoding='utf-8') as f:
        rd = json.load(f)
    start = rd['records'][0]['date']
    print(f"  {code}: {start}")

# CSI 300 in the same period
ixp = os.path.join(dd, '000300.json')
with open(ixp, encoding='utf-8') as f:
    ix = json.load(f)
ixdf = pd.DataFrame(ix['records'])
ixdf['date'] = pd.to_datetime(ixdf['date'])
ixdf = ixdf.sort_values('date')
ixdf = ixdf[ixdf['date'] >= '2015-01-01']
ixdf = ixdf[ixdf['date'] <= '2026-07-14']
print(f"\nCSI 300: {ixdf.iloc[0]['date'].date()} ~ {ixdf.iloc[-1]['date'].date()}")
print(f"  {ixdf.iloc[0]['close']:.0f} -> {ixdf.iloc[-1]['close']:.0f}")
print(f"  Return: {(ixdf.iloc[-1]['close']/ixdf.iloc[0]['close']-1)*100:.1f}%")
ixr = ixdf['close'].pct_change().dropna()
print(f"  Ann Sharpe: {ixr.mean()/ixr.std()*np.sqrt(252):.3f}")
ixdf['cmax'] = ixdf['close'].cummax()
ixdf['dd'] = (ixdf['close'] / ixdf['cmax'] - 1) * 100
print(f"  Max DD: {ixdf['dd'].min():.1f}%")
