# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

dates = pd.date_range('2019-01-01', '2026-07-10', freq='5D')
sectors = ['宽基A股', '红利策略', '商品/周期/资源', '金融', '消费']
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
print('raw_df date dtype:', raw_df['date'].dtype)
print('raw_df date sample:', raw_df['date'].iloc[0], type(raw_df['date'].iloc[0]))
print('raw_df行数:', len(raw_df))

agg_df = raw_df.groupby(['date', 'sector']).agg(
    sector_close=('close', 'mean'),
    peTTM_mean=('peTTM_mean', 'mean'),
    pbMRQ_mean=('pbMRQ_mean', 'mean'),
    n_etfs=('code', 'count'),
    atr=('atr', 'mean'),
).reset_index()
print('agg_df date dtype:', agg_df['date'].dtype)
print('agg_df date sample:', agg_df['date'].iloc[0], type(agg_df['date'].iloc[0]))
print('agg_df行数:', len(agg_df))

agg_df['date'] = pd.to_datetime(agg_df['date'])
print('after convert date dtype:', agg_df['date'].dtype)
print('after convert date sample:', agg_df['date'].iloc[0])

bt_start = pd.Timestamp('2020-01-01')
bt_end = pd.Timestamp('2026-07-10')
bt_df = agg_df[(agg_df['date'] >= bt_start) & (agg_df['date'] <= bt_end)]
print('bt_df行数:', len(bt_df))
print('bt_df date sample:', bt_df['date'].iloc[0] if len(bt_df)>0 else 'empty')
