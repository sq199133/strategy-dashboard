# -*- coding: utf-8 -*-
"""测试BaoStock ETF数据可用日期范围"""
import baostock as bs
import time

bs.login()
test_dates = [
    '2026-07-10', '2026-07-05', '2026-06-28', '2026-06-20',
    '2026-01-01', '2025-12-31', '2025-06-30', '2025-01-01',
    '2024-12-31', '2024-06-30', '2024-01-01',
    '2023-12-31', '2023-06-30', '2023-01-01',
]

for d in test_dates:
    rs = bs.query_daily_history_k_ETF(d)
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    count = len(data)
    # 检查有多少有PE数据
    pe_valid = sum(1 for r in data if r[13])  # peTTM is field index 13
    print(f"{d}: {count} rows, {pe_valid} with PE")
    time.sleep(0.3)

bs.logout()
