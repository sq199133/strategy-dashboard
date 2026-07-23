# -*- coding: utf-8 -*-
"""Quick test of the akshare ETF downloader"""
import akshare as ak
import pandas as pd
import time

# Test a few ETFs
codes = [
    ('160723', '嘉实原油LOF', 'sh160723'),
    ('510300', '沪深300ETF华泰', 'sh510300'),
    ('518880', '黄金ETF华夏', 'sh518880'),
    ('159995', '芯片ETF华夏', 'sz159995'),
]

for code_raw, name, code_sina in codes:
    try:
        df = ak.fund_etf_hist_sina(symbol=code_sina)
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            print(f"{code_raw} ({name}): {len(df)} rows, "
                  f"{df['date'].min().date()} ~ {df['date'].max().date()}")
        else:
            print(f"{code_raw}: No data")
    except Exception as e:
        print(f"{code_raw}: Error - {e}")
    time.sleep(0.5)
