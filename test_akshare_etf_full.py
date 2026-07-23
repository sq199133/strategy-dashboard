# -*- coding: utf-8 -*-
"""测试AkShare ETF数据能力"""
import akshare as ak
import time

# 1. ETF历史K线 (Sina) - 测试多只ETF
print("=== ETF历史K线 (Sina) ===")
for code in ['sh510300', 'sh510500', 'sh518880', 'sz159919']:
    try:
        df = ak.fund_etf_hist_sina(symbol=code)
        print(f'{code}: {len(df)} rows, date range: {df["date"].min()} ~ {df["date"].max()}')
        print(f'  cols: {list(df.columns)}')
    except Exception as e:
        print(f'{code}: error - {e}')
    time.sleep(0.5)

# 2. ETF实时数据 - 查看所有可用列
print("\n=== ETF实时数据列名 ===")
df_spot = ak.fund_etf_spot_em()
print(f'Total ETFs: {len(df_spot)}')
print('All columns:')
for c in df_spot.columns:
    print(f'  {c}')
