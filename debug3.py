# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

# Simulate exactly what happens in the strategy script
dates = pd.date_range('2019-01-01', '2026-07-10', freq='5D')
sectors = ['宽基A股', '红利策略', '商品/周期/资源', '金融', '消费', 
           '医药生物', '科技/TMT/AI', '制造/基建/公用', '芯片半导体', '港股/中概']
np.random.seed(42)
data = []
prev_prices = {s: 1.0 for s in sectors}
for date in dates:
    for sector in sectors:
        prev = prev_prices[sector]
        noise = np.random.normal(0, 0.015)
        trend = 0.0003
        ret = trend + noise
        close = prev * (1 + ret)
        prev_prices[sector] = close
        data.append({'date': date, 'code': f'demo.{sector}', 'sector': sector, 'close': close,
                     'volume': 1000000, 'peTTM_mean': 15.0, 'pbMRQ_mean': 1.5, 'atr': 0.01,
                     'n_etfs': 5})

raw_df = pd.DataFrame(data)
sector_daily = raw_df.copy()
sector_daily['date'] = pd.to_datetime(sector_daily['date'])
agg_df = sector_daily.groupby(['date', 'sector']).agg(
    sector_close=('close', 'mean'),
    volume_sum=('volume', 'sum'),
    peTTM_mean=('peTTM_mean', 'mean'),
    pbMRQ_mean=('pbMRQ_mean', 'mean'),
    n_etfs=('code', 'count'),
    atr=('atr', 'mean'),
).reset_index()
agg_df = agg_df.sort_values(['sector', 'date'])
agg_df['return'] = agg_df.groupby('sector')['sector_close'].pct_change()

print('agg_df行数:', len(agg_df))
print('agg_df date dtype:', agg_df['date'].dtype)
print('agg_df date sample:', agg_df['date'].iloc[0])

# Now simulate calc_valuation_percentile
sector_df = agg_df.copy()
sector_df['date'] = pd.to_datetime(sector_df['date'])
sector_df = sector_df.sort_values(['sector', 'date']).reset_index(drop=True)

print('after reset_index:')
print('sector_df行数:', len(sector_df))
print('sector_df date dtype:', sector_df['date'].dtype)
print('sector_df date sample:', sector_df['date'].iloc[0])

# Add pe_pct column
sector_df['pe_pct'] = np.nan
sector_df['pb_pct'] = np.nan
sector_df['valuation_score'] = 0.5

print('after adding columns:')
print('sector_df行数:', len(sector_df))
print('sector_df date dtype:', sector_df['date'].dtype)

# Now simulate calc_momentum_atr
def calc_momentum_atr(df, momentum_days=12):
    df = df.copy()
    df = df.sort_values(['sector', 'date'])
    df['momentum'] = df.groupby('sector')['return'].transform(
        lambda x: x.rolling(momentum_days, min_periods=5).sum()
    )
    df['atr_pct'] = df.groupby('sector')['atr'].transform(
        lambda x: x.rolling(60, min_periods=20).apply(
            lambda arr: float(pd.Series(arr).rank(pct=True).iloc[-1]) if not np.isnan(arr[-1]) else np.nan,
            raw=True
        )
    )
    return df

sector_df = calc_momentum_atr(sector_df, momentum_days=12)
print('after momentum:')
print('sector_df行数:', len(sector_df))
print('sector_df date dtype:', sector_df['date'].dtype)

# Now filter
bt_start = pd.Timestamp('2020-01-01')
bt_end = pd.Timestamp('2026-07-10')
sector_df['date'] = pd.to_datetime(sector_df['date'])
print('bt_start:', bt_start, 'tz:', bt_start.tz)
print('sector_df date sample:', sector_df['date'].iloc[0], 'tz:', sector_df['date'].iloc[0].tz)

mask_gt = sector_df['date'] >= bt_start
mask_lt = sector_df['date'] <= bt_end
print('mask_gt sum:', mask_gt.sum())
print('mask_lt sum:', mask_lt.sum())

bt_df = sector_df[(sector_df['date'] >= bt_start) & (sector_df['date'] <= bt_end)].copy()
print('bt_df行数:', len(bt_df))
if len(bt_df) > 0:
    print('bt_df date sample:', bt_df['date'].iloc[0])
else:
    print('BT DF IS EMPTY!')
    # Show some dates near the boundary
    near_start = sector_df[sector_df['date'] < bt_start].tail(5)
    near_end = sector_df[sector_df['date'] > bt_end].head(5)
    print('dates just before 2020-01-01:', near_start['date'].tolist())
    print('dates just after bt_end:', near_end['date'].tolist())
