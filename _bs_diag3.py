# -*- coding: utf-8 -*-
"""诊断BaoStock各接口PE可用性"""
import baostock as bs, sys

bs.login()
print('login ok', flush=True)

# 测试月频日期范围
tests = [
    ('sh.600000', '2025-01-01', '2025-12-31', 'm'),
    ('sh.600000', '2025-01-01', '2025-06-30', 'm'),
    ('sh.600000', '2024-01-01', '2024-12-31', 'm'),
    ('sh.600000', '2020-01-01', '2025-12-31', 'm'),
    ('sh.600000', '2018-01-01', '2025-12-31', 'm'),
    ('sh.600000', '2025-01-01', '2025-12-31', 'w'),
    ('sh.600000', '2025-01-01', '2025-03-31', 'm'),
    ('sh.600000', '2025-01-01', '2025-01-31', 'm'),
]

for code, s, e, freq in tests:
    rs = bs.query_history_k_data_plus(code, 'date,code,close,peTTM,pbMRQ', s, e, freq)
    n = 0
    while rs.error_code == '0' and rs.next(): n += 1
    print(f'{code} {s}~{e} {freq}: err={rs.error_code} fields={rs.fields[:5]} rows={n}', flush=True)

# 测试 query_fina_indicator
print('\nquery_fina_indicator test:', flush=True)
rs = bs.query_fina_indicator('sh.600000', start_date='2024-01-01', end_date='2025-12-31')
print(f'  err={rs.error_code} fields={rs.fields[:8]}', flush=True)
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'  rows={len(rows)}', flush=True)
if rows: print(f'  sample={rows[0]}', flush=True)

# 测试 query_profit_data
print('\nquery_profit_data test:', flush=True)
rs = bs.query_profit_data('sh.600000', year='2024', quarter='4')
print(f'  err={rs.error_code} fields={rs.fields}', flush=True)
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'  rows={len(rows)}', flush=True)
if rows: print(f'  sample={rows[0]}', flush=True)

bs.logout()
