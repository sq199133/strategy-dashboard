# -*- coding: utf-8 -*-
"""验证PE数据覆盖率，找出哪些股票有PE数据"""
import os, time, baostock as bs, pandas as pd, numpy as np

OUT = r'D:\QClaw_Trading\data\index_val'
os.makedirs(OUT, exist_ok=True)

bs.login()

# 获取HS300成分股
rs = bs.query_hs300_stocks(date='2026-07-10')
hs300 = []
while rs.error_code == '0' and rs.next():
    hs300.append(rs.get_row_data())
df300 = pd.DataFrame(hs300, columns=rs.fields)
codes = df300['code'].tolist()

# 随机抽20只测试PE数据可用性
np.random.seed(42)
sample = np.random.choice(codes, min(20, len(codes)), replace=False).tolist()

print(f'测试{len(sample)}只股票PE数据...')
t0 = time.time()
results = []
for code in sample:
    rs = bs.query_history_k_data_plus(code,
        'date,code,close,peTTM,pbMRQ',
        start_date='2020-01-01', end_date='2026-07-10', frequency='m')
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    err = rs.error_code
    fields = list(rs.fields)
    has_pe = 'peTTM' in fields
    n_rows = len(rows)
    n_pe_valid = 0
    if rows and has_pe:
        tmp = pd.DataFrame(rows, columns=fields)
        tmp['peTTM'] = pd.to_numeric(tmp['peTTM'], errors='coerce')
        n_pe_valid = tmp['peTTM'].notna().sum()
    results.append({'code': code, 'err': err, 'fields': str(fields[:5]), 'n_rows': n_rows, 'has_pe': has_pe, 'n_pe_valid': n_pe_valid})
    time.sleep(0.06)

elapsed = time.time() - t0
df_res = pd.DataFrame(results)
print(df_res.to_string(index=False))
print(f'\n总耗时: {elapsed:.1f}秒')
print(f'有peTTM字段: {df_res["has_pe"].sum()}/{len(df_res)}')
print(f'PE有效记录>0: {(df_res["n_pe_valid"]>0).sum()}/{len(df_res)}')

# 保存结果
df_res.to_csv(os.path.join(OUT, 'pe_coverage_test.csv'), index=False)

# 如果PE覆盖率足够，开始批量下载
pe_coverage = df_res['n_pe_valid'].sum() / max(1, df_res['n_rows'].sum()) if len(df_res) > 0 else 0
print(f'\nPE覆盖率: {pe_coverage:.1%}')

bs.logout()
