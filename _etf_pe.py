# -*- coding: utf-8 -*-
import pandas as pd
df = pd.read_csv(r'D:\QClaw_Trading\data\baostock_etf\combined.csv')
print('字段:', list(df.columns))
print('行数:', len(df))
print('ETF数量:', df['code'].nunique())
print()
print('peTTM有效:', df['peTTM'].notna().sum(), '/', len(df))
print('pbMRQ有效:', df['pbMRQ'].notna().sum(), '/', len(df))
print()
print(df[['code','date','close','volume','peTTM','pbMRQ']].head(10).to_string())
# 看volume范围
df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
print()
print('volume统计:', df['volume'].describe())
# 有多少ETF volume>0
print('volume>0:', (df['volume']>0).sum())
