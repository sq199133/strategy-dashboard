# -*- coding: utf-8 -*-
"""测试BaoStock ETF历史数据可用接口"""
import baostock as bs
import time

bs.login()

# 测试 query_history_k_data_plus（个股历史K线，可能支持ETF）
print("=== query_history_k_data_plus ===")
rs = bs.query_history_k_data_plus("sh.510300",
    "date,code,open,high,low,close,volume,amount,peTTM,pbMRQ",
    start_date='2025-01-01', end_date='2026-07-10', frequency="daily")
print('error:', rs.error_code, rs.error_msg)
print('fields:', rs.fields)
data = []
while rs.next():
    data.append(rs.get_row_data())
print(f'rows: {len(data)}')
for r in data[:5]:
    print(r)

time.sleep(1)

# 测试 query_profit_data（财务数据）
print("\n=== query_daily_k_data ===")
rs2 = bs.query_daily_k_data("sh.510300",
    "date,code,open,high,low,close,volume,amount,pctChg",
    start_date='2025-01-01', end_date='2026-07-10')
print('error:', rs2.error_code, rs2.error_msg)
print('fields:', rs2.fields)
data2 = []
while rs2.next():
    data2.append(rs2.get_row_data())
print(f'rows: {len(data2)}')
for r in data2[:5]:
    print(r)

bs.logout()
