# -*- coding: utf-8 -*-
"""修复版：批量下载宽基指数成分股PE/PB"""
import os, time, baostock as bs, pandas as pd, numpy as np

np.random.seed(42)
OUT = r'D:\QClaw_Trading\data\index_val'
os.makedirs(OUT, exist_ok=True)

bs.login()

# 测试单只股票
print('=== 单只股票月频测试 ===')
rs = bs.query_history_k_data_plus('sh.600000',
    'date,code,open,high,low,close,volume,peTTM,pbMRQ,turn',
    start_date='2015-01-01', end_date='2026-07-10', frequency='m')
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
print(f'字段: {rs.fields}')
df_test = pd.DataFrame(rows, columns=rs.fields)
print(df_test.head(3).to_string())
if 'peTTM' in df_test.columns:
    df_test['peTTM'] = pd.to_numeric(df_test['peTTM'], errors='coerce')
    print(f'有效PE: {df_test["peTTM"].notna().sum()} / {len(df_test)}')

# 获取成分股列表
print('\n=== 获取成分股 ===')
rs = bs.query_hs300_stocks(date='2026-07-10')
hs300 = []
while rs.error_code == '0' and rs.next():
    hs300.append(rs.get_row_data())
df300 = pd.DataFrame(hs300, columns=rs.fields)
hs300_codes = df300['code'].tolist()
print(f'沪深300: {len(hs300_codes)} 只')

# 批量下载HS300前100只（分2批，每批50只，估算全量时间）
print('\n=== 批量下载测试（沪深300前50只）===')
sample = hs300_codes[:50]
t0 = time.time()
results = []
for i, code in enumerate(sample):
    rs = bs.query_history_k_data_plus(code,
        'date,code,open,high,low,close,volume,peTTM,pbMRQ',
        start_date='2015-01-01', end_date='2026-07-10', frequency='m')
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    if rows:
        tmp = pd.DataFrame(rows, columns=rs.fields)
        results.append(tmp)
    if (i+1) % 10 == 0:
        elapsed = time.time() - t0
        eta = elapsed/(i+1)*(len(sample)-i-1)
        print(f'  {i+1}/{len(sample)} 耗时{elapsed:.1f}s, 预计剩余{eta:.0f}s')
    time.sleep(0.07)

elapsed = time.time() - t0
print(f'50只耗时: {elapsed:.1f}秒')
total_est = elapsed/50*(300+500+300)  # HS300+ZZ500+CIT1000
print(f'预计全量(HS300+ZZ500+成分代表性300): {total_est:.0f}秒 = {total_est/60:.1f}分钟')

bs.logout()

if results:
    combined = pd.concat(results, ignore_index=True)
    combined['date'] = pd.to_datetime(combined['date'])
    for c in ['close', 'volume', 'peTTM', 'pbMRQ']:
        if c in combined.columns:
            combined[c] = pd.to_numeric(combined[c], errors='coerce')
    
    print(f'\n合并数据: {len(combined)}行')
    print(f'有效PE记录: {combined["peTTM"].notna().sum()} / {len(combined)}')
    
    # 按月聚合（中位数）
    monthly = combined.groupby('date').agg(
        pe_median=('peTTM', 'median'),
        pb_median=('pbMRQ', 'median'),
        stock_count=('code', 'count'),
        avg_pe=('peTTM', 'mean'),
    ).reset_index().sort_values('date')
    
    # PE分位
    pe_vals = monthly['pe_median'].values
    pct = np.full(len(pe_vals), np.nan)
    for i in range(60, len(pe_vals)):
        window = pe_vals[max(0, i-60):i]
        valid = window[~np.isnan(window) & (window > 0)]
        if len(valid) >= 36:
            pct[i] = (valid < pe_vals[i]).sum() / len(valid)
    monthly['pe_pct'] = pct
    
    monthly_valid = monthly.dropna(subset=['pe_pct'])
    print(f'\n有效PE分位: {len(monthly_valid)}月 ({monthly_valid["date"].min()} ~ {monthly_valid["date"].max()})')
    print(monthly_valid[['date','pe_median','pe_pct']].tail(12).to_string())
    
    # 保存
    monthly.to_csv(os.path.join(OUT, 'hs300_pe_50sample.csv'), index=False)
    print(f'\n已保存: {OUT}/hs300_pe_50sample.csv')
