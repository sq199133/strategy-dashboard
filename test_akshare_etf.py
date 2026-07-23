# -*- coding: utf-8 -*-
import akshare as ak
print('akshare version:', ak.__version__)

# 测试ETF历史K线 - 东方财富网
try:
    df = ak.fund_etf_hist_em(symbol='510300', period='daily', start_date='20250601', end_date='20260710')
    print('fund_etf_hist_em success!')
    print('rows:', len(df))
    print('columns:', list(df.columns))
    print(df.head(3))
except Exception as e:
    print('fund_etf_hist_em error:', e)

# 测试ETF PE/PB
try:
    df2 = ak.fund_etf_spot_em()
    print('\nfund_etf_spot_em success!')
    print('rows:', len(df2))
    print('columns:', list(df2.columns)[:10])
    print(df2.head(2))
except Exception as e:
    print('fund_etf_spot_em error:', e)
