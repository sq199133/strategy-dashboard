# -*- coding: utf-8 -*-
import baostock as bs
import sys

print('start', flush=True)
sys.stdout.flush()

rs = bs.login()
print(f'login: {rs.error_code}', flush=True)
sys.stdout.flush()

# Test simple
print('Test1...', flush=True)
rs = bs.query_history_k_data_plus('sh.600000', 'date,code,close', '2025-01-01', '2025-12-31', 'd')
print(f'  err={rs.error_code} fields={rs.fields}', flush=True)
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'  rows={len(rows)}', flush=True)
if rows:
    print(f'  sample={rows[0]}', flush=True)

print('Test2 peTTM...', flush=True)
rs = bs.query_history_k_data_plus('sh.600000', 'date,code,close,peTTM', '2025-01-01', '2025-12-31', 'd')
print(f'  err={rs.error_code} fields={rs.fields}', flush=True)

print('Test3 monthly...', flush=True)
rs = bs.query_history_k_data_plus('sh.600000', 'date,code,close,peTTM', '2024-01-01', '2025-12-31', 'm')
print(f'  err={rs.error_code} fields={rs.fields}', flush=True)
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'  rows={len(rows)}', flush=True)
if rows:
    print(f'  sample={rows[0]}', flush=True)

bs.logout()
print('done', flush=True)
