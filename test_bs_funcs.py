# -*- coding: utf-8 -*-
import baostock as bs
funcs = [a for a in dir(bs) if 'query' in a.lower() or 'history' in a.lower() or 'daily' in a.lower() or 'k_' in a.lower()]
print('Query/History/Daily functions:')
for f in sorted(funcs):
    print(f'  {f}')

# Test query_history_k_data for ETF
bs.login()
rs = bs.query_history_k_data("sh.510300",
    "date,code,open,high,low,close,volume,amount",
    start_date='2025-06-01', end_date='2026-07-10', frequency="d")
print(f'\nquery_history_k_data error: {rs.error_code} {rs.error_msg}')
print(f'fields: {rs.fields}')
data = []
while rs.next():
    data.append(rs.get_row_data())
print(f'rows: {len(data)}')
for r in data[:3]:
    print(r)
bs.logout()
