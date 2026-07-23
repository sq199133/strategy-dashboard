# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

dates = pd.date_range('2019-01-01', '2026-07-10', freq='5D')
sectors = ['宽基A股', '红利策略']
np.random.seed(42)
data = []
for date in dates:
    for sector in sectors:
        data.append({'date': date, 'sector': sector, 'close': 1.0, 
                     'volume': 1000000, 'peTTM_mean': 15.0, 'pbMRQ_mean': 1.5, 
                     'atr': 0.01, 'n_etfs': 5})

raw_df = pd.DataFrame(data)
agg_df = raw_df.groupby(['date', 'sector']).agg(
    sector_close=('close', 'mean'),
    volume_sum=('volume', 'sum'),
    peTTM_mean=('peTTM_mean', 'mean'),
    pbMRQ_mean=('pbMRQ_mean', 'mean'),
    n_etfs=('code', 'count'),
    atr=('atr', 'mean'),
).reset_index()
agg_df = agg_df.sort_values(['sector', 'date'])
agg_df['return'] = agg_df.groupby('sector')['sector_close'].pct_change()

sector_df = agg_df.copy()
sector_df['date'] = pd.to_datetime(sector_df['date']).dt.normalize()

# Simulate calc_valuation_percentile
sector_df['pe_pct'] = 0.5
sector_df['pb_pct'] = 0.5
sector_df['valuation_score'] = 0.5

# Simulate calc_momentum_atr
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
print('After momentum:')
print('  rows:', len(sector_df))
print('  date dtype:', sector_df['date'].dtype)
print('  date sample:', sector_df['date'].iloc[0])

start_str = '2020-01-01'
end_str = '2026-07-10'
date_str = sector_df['date'].dt.strftime('%Y-%m-%d')
print('date_str sample:', date_str.iloc[0], type(date_str.iloc[0]))

mask = (date_str >= start_str) & (date_str <= end_str)
print('mask True:', mask.sum())

bt_df = sector_df.loc[mask].copy()
print('bt_df rows:', len(bt_df))
print('bt_df cols:', list(bt_df.columns))
