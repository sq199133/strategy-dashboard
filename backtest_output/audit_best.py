import json, os, pandas as pd, numpy as np

d = 'D:/QClaw_Trading/backtest_output/factor_run_20260713_230732'
data_dir = 'D:/QClaw_Trading/data/history/'

prefix = '低波动12m_12m_top5'
tr = pd.read_csv(os.path.join(d, f'{prefix}_trades.csv'))

tr['symbol_str'] = tr['symbol'].astype(str)
gold_mask = tr['symbol_str'].str.startswith('518')
gold_trades = tr[gold_mask]
print(f'Gold ETF trades: {len(gold_trades)} / {len(tr)}')
print(f'Gold pnl: {gold_trades["pnl"].sum():.0f} / {tr["pnl"].sum():.0f} = {gold_trades["pnl"].sum()/tr["pnl"].sum()*100:.1f}%')

# Gold price
gf = os.path.join(data_dir, '518880.json')
with open(gf, encoding='utf-8') as f:
    gd = json.load(f)
recs = pd.DataFrame(gd['records'])
recs['date'] = pd.to_datetime(recs['date'])
recs = recs.sort_values('date')
recs = recs[recs['date'] >= '2021-01-01']
print(f'\nGold 518880 2021~2026: close {recs.iloc[0]["close"]:.3f} -> {recs.iloc[-1]["close"]:.3f}')
print(f'Return: {(recs.iloc[-1]["close"]/recs.iloc[0]["close"]-1)*100:.1f}%')
ret = recs['close'].pct_change().dropna()
print(f'Ann vol: {ret.std()*np.sqrt(252)*100:.1f}%')

# CSI 300
idx = pd.read_json(os.path.join(data_dir, '000300.json'))
# Actually records is nested
with open(os.path.join(data_dir, '000300.json'), encoding='utf-8') as f:
    ix = json.load(f)
ix_df = pd.DataFrame(ix['records'])
ix_df['date'] = pd.to_datetime(ix_df['date'])
ix_df = ix_df.sort_values('date')
ix_df = ix_df[ix_df['date'] >= '2021-01-01']
print(f'\nCSI 300 2021~2026: close {ix_df.iloc[0]["close"]:.0f} -> {ix_df.iloc[-1]["close"]:.0f}')
print(f'Return: {(ix_df.iloc[-1]["close"]/ix_df.iloc[0]["close"]-1)*100:.1f}%')
ixr = ix_df['close'].pct_change().dropna()
print(f'Sharpe (annual): {ixr.mean()/ixr.std()*np.sqrt(252):.2f}')

# Multi-factor gold check
print('\n=== Multi 动量+低波 top5 ===')
for f in os.listdir(d):
    if '动量+低波' in f and 'top5' in f and 'trades' in f:
        tr2 = pd.read_csv(os.path.join(d, f))
        tr2['sym'] = tr2['symbol'].astype(str)
        gm = tr2['sym'].str.startswith('518')
        print(f'Gold trades: {gm.sum()} / {len(tr2)}')
        print(f'Gold pnl: {tr2.loc[gm,"pnl"].sum():.0f} / {tr2["pnl"].sum():.0f} = {tr2.loc[gm,"pnl"].sum()/tr2["pnl"].sum()*100:.1f}%')
        break

# Monthly win rate check
eq = pd.read_csv(os.path.join(d, f'{prefix}_equity.csv'))
eq['ym'] = pd.to_datetime(eq['date']).dt.to_period('M')
monthly = eq.groupby('ym')['value'].last()
mr = monthly.pct_change().dropna()
pos = (mr > 0).sum()
neg = (mr <= 0).sum()
print(f'\nMonthly win rate: {pos}/{pos+neg} = {pos/(pos+neg)*100:.1f}%')
print(f'Avg monthly return: {mr.mean()*100:.2f}%')
print(f'Best month: {mr.max()*100:.2f}%')
print(f'Worst month: {mr.min()*100:.2f}%')

# Other non-gold low vol ETFs top holdings
non_gold = tr[~gold_mask]
print(f'\nNon-gold positions: {non_gold["symbol_str"].nunique()} symbols, {len(non_gold)} trades')
print(f'Non-gold pnl: {non_gold["pnl"].sum():.0f}')
vc = non_gold['symbol_str'].value_counts().head(15)
for s, c in vc.items():
    spnl = non_gold[non_gold['symbol_str']==s]['pnl'].sum()
    print(f'  {s}: {c} trades, pnl={spnl:.0f}')
