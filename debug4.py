# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np

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
    peTTM_mean=('peTTM_mean', 'mean'),
    pbMRQ_mean=('pbMRQ_mean', 'mean'),
    n_etfs=('code', 'count'),
    atr=('atr', 'mean'),
).reset_index()
agg_df = agg_df.sort_values(['sector', 'date'])
agg_df['return'] = agg_df.groupby('sector')['sector_close'].pct_change()
agg_df['pe_pct'] = np.nan
agg_df['pb_pct'] = np.nan
agg_df['valuation_score'] = 0.5
agg_df['momentum'] = agg_df.groupby('sector')['return'].transform(lambda x: x.rolling(12, min_periods=5).sum())
agg_df['atr_pct'] = 0.5

sector_df = agg_df.copy()

# Now try the exact filter from main()
bt_start = pd.Timestamp('2020-01-01')
bt_end = pd.Timestamp('2026-07-10')
sector_df['date'] = pd.to_datetime(sector_df['date']).dt.normalize()
print(f"After normalize: dtype={sector_df['date'].dtype}, sample={sector_df['date'].iloc[0]}")

# Integer method
start_int = bt_start.value // (24*3600*10**9)
end_int = bt_end.value // (24*3600*10**9)
date_int = sector_df['date'].values.view('int64') // (24*3600*10**9)
print(f"start_int={start_int}, end_int={end_int}, date_int sample={date_int[:3]}")
mask = (date_int >= start_int) & (date_int <= end_int)
print(f"mask true: {mask.sum()}")
bt_df = sector_df.loc[mask].copy()
print(f"bt_df rows: {len(bt_df)}")
