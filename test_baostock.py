# -*- coding: utf-8 -*-
import baostock as bs
import sys

print('Starting test...', flush=True)
lg = bs.login()
print('login:', lg.error_msg, flush=True)

rs = bs.query_daily_history_k_ETF('2026-07-10')
print('error_code:', rs.error_code, flush=True)
print('error_msg:', rs.error_msg, flush=True)
print('fields:', rs.fields, flush=True)

data = []
while rs.next():
    row = rs.get_row_data()
    data.append(row)
    if len(data) <= 3:
        print(row, flush=True)

print('total rows:', len(data), flush=True)
bs.logout()
print('done', flush=True)
