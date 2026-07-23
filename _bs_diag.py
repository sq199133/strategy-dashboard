# -*- coding: utf-8 -*-
"""诊断BaoStock PE数据可用性"""
import baostock as bs, pandas as pd

bs.login()
print(f'登录状态: {bs.error_code}')

# 测试1: 简单K线(无PE)
print('\n--- 测试1: query_history_k_data_plus 纯价格 ---')
rs = bs.query_history_k_data_plus('sh.600000',
    'date,code,close',
    start_date='2025-01-01', end_date='2025-12-31', frequency='d')
print(f'错误: {rs.error_code} {rs.error_msg}')
print(f'字段: {rs.fields}')
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'行数: {len(rows)}')
if rows: print(rows[0])

# 测试2: 加PE字段
print('\n--- 测试2: 加peTTM ---')
rs2 = bs.query_history_k_data_plus('sh.600000',
    'date,code,close,peTTM',
    start_date='2025-01-01', end_date='2025-12-31', frequency='d')
print(f'错误: {rs2.error_code} {rs2.error_msg}')
print(f'字段: {rs2.fields}')
rows2 = []
while rs2.error_code == '0' and rs2.next():
    rows2.append(rs2.get_row_data())
print(f'行数: {len(rows2)}')
if rows2: print(rows2[0])

# 测试3: 用月频
print('\n--- 测试3: 月频 ---')
rs3 = bs.query_history_k_data_plus('sh.600000',
    'date,code,close,peTTM,pbMRQ',
    start_date='2024-01-01', end_date='2025-12-31', frequency='m')
print(f'错误: {rs3.error_code} {rs3.error_msg}')
print(f'字段: {rs3.fields}')
rows3 = []
while rs3.error_code == '0' and rs3.next():
    rows3.append(rs3.get_row_data())
print(f'行数: {len(rows3)}')
if rows3: print(rows3[:3])

# 测试4: 用query_k_data_step
print('\n--- 测试4: query_k_data_step ---')
rs4 = bs.query_k_data_step('sh.600000', '2025-01-01', '2025-12-31')
print(f'错误: {rs4.error_code} {rs4.error_msg}')
print(f'字段: {rs4.fields}')
rows4 = []
while rs4.error_code == '0' and rs4.next():
    rows4.append(rs4.get_row_data())
print(f'行数: {len(rows4)}')
if rows4: print(rows4[0])

# 测试5: 换一只科创板
print('\n--- 测试5: 科创板 sh.688001 ---')
rs5 = bs.query_history_k_data_plus('sh.688001',
    'date,code,close,peTTM',
    start_date='2023-01-01', end_date='2025-12-31', frequency='m')
print(f'错误: {rs5.error_code} {rs5.error_msg}')
print(f'字段: {rs5.fields}')
rows5 = []
while rs5.error_code == '0' and rs5.next():
    rows5.append(rs5.get_row_data())
print(f'行数: {len(rows5)}')
if rows5: print(rows5[:2])

# 测试6: query_stock_industry
print('\n--- 测试6: 行业分类 ---')
rs6 = bs.query_stock_industry()
print(f'错误: {rs6.error_code} {rs6.error_msg}')
print(f'字段: {rs6.fields}')
rows6 = []
while rs6.error_code == '0' and rs6.next():
    rows6.append(rs6.get_row_data())
print(f'行数: {len(rows6)}')
if rows6: print(rows6[:2])

bs.logout()
