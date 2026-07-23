# -*- coding: utf-8 -*-
"""快速验证 + 批量下载宽基指数成分股PE/PB"""
import os, time, baostock as bs, pandas as pd, numpy as np

np.random.seed(42)
OUT = r'D:\QClaw_Trading\data\index_val'
os.makedirs(OUT, exist_ok=True)

bs.login()

# 测试各指数成分股
tests = [
    ('sh.000300', 'query_hs300_stocks', '2026-07-10'),
    ('sh.000905', 'query_zz500_stocks', '2026-07-10'),
    ('sz.399006', 'query_history_k_data_plus_sz399006', '2026-01-01'),
]

results = {}

# HS300
print('=== HS300 成分股 ===')
rs = bs.query_hs300_stocks(date='2026-07-10')
hs300 = []
while rs.error_code == '0' and rs.next():
    hs300.append(rs.get_row_data())
df300 = pd.DataFrame(hs300, columns=rs.fields)
print(f'沪深300成分股: {len(df300)} 只')
print(df300.head(3).to_string())
results['hs300'] = df300['code'].tolist()

# ZZ500
print('\n=== ZZ500 成分股 ===')
rs = bs.query_zz500_stocks(date='2026-07-10')
zz500 = []
while rs.error_code == '0' and rs.next():
    zz500.append(rs.get_row_data())
df500 = pd.DataFrame(zz500, columns=rs.fields)
print(f'中证500成分股: {len(df500)} 只')
print(df500.head(3).to_string())
results['zz500'] = df500['code'].tolist()

# 测试单只股票月频PE
print('\n=== 单只股票月频PE测试 ===')
rs = bs.query_history_k_data_plus('sh.600000',
    'date,code,close,peTTM,pbMRQ,turn',
    start_date='2015-01-01', end_date='2026-07-10', frequency='m')
rows = []
while rs.error_code == '0' and rs.next():
    rows.append(rs.get_row_data())
df = pd.DataFrame(rows, columns=rs.fields)
df['peTTM'] = pd.to_numeric(df['peTTM'], errors='coerce')
print(f'浦发银行月频数据: {len(df)}月')
valid_pe = df[df['peTTM'] > 0]['peTTM']
print(f'有效PE月数: {len(valid_pe)} / {len(df)}')
if len(valid_pe) > 0:
    print(f'PE范围: {valid_pe.min():.2f} ~ {valid_pe.max():.2f}')

# 测试批量月频PE（30只样本，估算全量时间）
print('\n=== 批量下载测试（HS300前30只）===')
sample_codes = df300['code'].tolist()[:30]
all_data = []
t0 = time.time()
for i, code in enumerate(sample_codes):
    rs = bs.query_history_k_data_plus(code,
        'date,code,close,peTTM,pbMRQ',
        start_date='2015-01-01', end_date='2026-07-10', frequency='m')
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    if rows:
        tmp = pd.DataFrame(rows, columns=rs.fields)
        all_data.append(tmp)
    if i % 5 == 4:
        elapsed = time.time() - t0
        eta = elapsed / (i+1) * (300 - i - 1)
        print(f'  {i+1}/30 已完成, 预计全量HS300还需{eta:.0f}秒')
    time.sleep(0.07)

elapsed = time.time() - t0
print(f'30只耗时: {elapsed:.1f}秒, 预计全量300只: {elapsed/30*300:.0f}秒')
print(f'预计3指数(HS300+ZZ500+CIT1000)全量: {elapsed/30*(300+500+100):.0f}秒')

bs.logout()

# 合并测试数据并计算PE分位
if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    combined['date'] = pd.to_datetime(combined['date'])
    combined['peTTM'] = pd.to_numeric(combined['peTTM'], errors='coerce')
    combined['close'] = pd.to_numeric(combined['close'], errors='coerce')
    combined['pbMRQ'] = pd.to_numeric(combined['pbMRQ'], errors='coerce')
    
    # 按月算中位数PE
    monthly = combined.groupby('date').agg(
        pe_median=('peTTM', 'median'),
        pb_median=('pbMRQ', 'median'),
        stock_count=('code', 'count'),
    ).reset_index()
    monthly = monthly.sort_values('date')
    
    # 计算滚动60月分位
    pe_vals = monthly['pe_median'].values
    pct = np.full(len(pe_vals), np.nan)
    for i in range(60, len(pe_vals)):
        window = pe_vals[max(0, i-60):i]
        valid = window[~np.isnan(window) & (window > 0)]
        if len(valid) >= 36:
            pct[i] = (valid < pe_vals[i]).sum() / len(valid)
    
    monthly['pe_pct'] = pct
    monthly_valid = monthly.dropna(subset=['pe_pct'])
    print(f'\n有效PE分位数据: {len(monthly_valid)}月')
    print(f'PE分位范围: {monthly_valid["pe_pct"].min():.2f} ~ {monthly_valid["pe_pct"].max():.2f}')
    print(f'最新PE分位: {monthly_valid.iloc[-1]["pe_pct"]:.2%}')
    print(monthly_valid[['date','pe_median','pe_pct']].tail(12).to_string())
    
    monthly.to_csv(os.path.join(OUT, 'hs300_pe_demo.csv'), index=False)
    print(f'\ndemo数据已保存: {OUT}/hs300_pe_demo.csv')
