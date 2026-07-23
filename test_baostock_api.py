# -*- coding: utf-8 -*-
"""测试BaoStock各ETF相关接口"""
import baostock as bs
import time

bs.login()

# 获取ETF基本信息
print("=== query_etf_list ===")
rs = bs.query_etf_list()
print('fields:', rs.fields)
data = []
while rs.next():
    data.append(rs.get_row_data())
print(f'ETF count: {len(data)}')
if data:
    print('sample:', data[:2])

time.sleep(1)

# 获取ETF日K线历史 - 测试不同frequency
print("\n=== query_history_k_data (ETF) ===")
# BaoStock ETF codes are like sh.510300, sz.159001
# Check what functions are available
funcs = [a for a in dir(bs) if 'query' in a.lower()]
print('Available query functions:', funcs)

# Try stock historical k data with ETF code
print("\n=== query_history_k_data (sh.510300) ===")
rs = bs.query_history_k_data("sh.510300",
    "date,code,open,high,low,close,volume,amount",
    start_date='2025-01-01', end_date='2026-07-10', frequency="d")
print('error:', rs.error_code, rs.error_msg)
print('fields:', rs.fields)
data2 = []
while rs.next():
    data2.append(rs.get_row_data())
print(f'rows: {len(data2)}')
for r in data2[:3]:
    print(r)

bs.logout()
