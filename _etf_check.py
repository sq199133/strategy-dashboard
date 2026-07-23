# -*- coding: utf-8 -*-
"""快速验证ETF数据 + 构建简化版估值动量回测"""
import os, baostock as bs, pandas as pd, numpy as np

bs.login()

# 1. 取今日全量ETF
rs = bs.query_daily_history_k_ETF(date='2026-07-10')
data = []
while rs.error_code == '0' and rs.next():
    data.append(rs.get_row_data())
etf_df = pd.DataFrame(data, columns=rs.fields)

# 过滤有效PE/PB
etf_df['peTTM'] = pd.to_numeric(etf_df['peTTM'], errors='coerce')
etf_df['pbMRQ'] = pd.to_numeric(etf_df['pbMRQ'], errors='coerce')
valid = etf_df[(etf_df['peTTM'] > 0) & (etf_df['pbMRQ'] > 0) & (etf_df['pbMRQ'] < 20)]
print(f'=== ETF数据概览 ===')
print(f'总ETF: {len(etf_df)}只, 有PE/PB: {len(valid)}只')
print(valid[['code','close','volume','peTTM','pbMRQ']].head(8).to_string())

# 2. 批量取近期数据（最近60天，每5天一次 = 12个日期）
# 找最近的交易日
dates = pd.date_range('2026-05-01', '2026-07-10', freq='5D').strftime('%Y-%m-%d').tolist()
all_data = []
for d in dates:
    rs = bs.query_daily_history_k_ETF(date=d)
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    if rows:
        tmp = pd.DataFrame(rows, columns=rs.fields)
        all_data.append(tmp)
        print(f'{d}: {len(tmp)}只')
    else:
        print(f'{d}: 无数据')

bs.logout()

if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    combined['peTTM'] = pd.to_numeric(combined['peTTM'], errors='coerce')
    combined['pbMRQ'] = pd.to_numeric(combined['pbMRQ'], errors='coerce')
    combined['volume'] = pd.to_numeric(combined['volume'], errors='coerce')
    combined['close'] = pd.to_numeric(combined['close'], errors='coerce')
    combined['date'] = pd.to_datetime(combined['date'])
    combined = combined.sort_values(['code', 'date'])
    os.makedirs(r'D:\QClaw_Trading\data\baostock_etf', exist_ok=True)
    combined.to_csv(r'D:\QClaw_Trading\data\baostock_etf\combined.csv', index=False)
    print(f'\n已保存 {len(combined)} 条到 combined.csv')
    
    # 3. 快速回测：用demo板块数据做验证
    print('\n=== 快速估值动量回测（Demo数据）===')
    sectors = ['宽基A股', '消费', '医药', '科技', '金融', '商品', '制造']
    np.random.seed(42)
    dates_list = pd.date_range('2020-01-01', '2026-07-10', freq='W-FRI').strftime('%Y-%m-%d').tolist()
    rows = []
    prev = {s: 100.0 for s in sectors}
    for d in dates_list:
        for s in sectors:
            ret = np.random.normal(0.002, 0.025)
            close = prev[s] * (1 + ret)
            prev[s] = close
            rows.append({'date': d, 'sector': s, 'close': close,
                        'peTTM_mean': np.random.uniform(10, 40),
                        'pbMRQ_mean': np.random.uniform(0.8, 4),
                        'atr_pct': np.random.uniform(0.3, 0.7)})
    
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['sector', 'date'])
    df['ret'] = df.groupby('sector')['close'].pct_change()
    df['mom'] = df.groupby('sector')['ret'].transform(lambda x: x.rolling(12, min_periods=5).sum())
    df['pe_pct'] = 0.5
    df['pb_pct'] = 0.5
    df['valuation_score'] = 0.5
    
    # 估值分位（简化：用peTTM的反向排名作为分位）
    df['pe_rank'] = df.groupby('date')['peTTM_mean'].rank(pct=True)
    df['pb_rank'] = df.groupby('date')['pbMRQ_mean'].rank(pct=True)
    df['valuation_score'] = (df['pe_rank'] + df['pb_rank']) / 2  # 低估值=低分
    
    # 策略
    results = {}
    
    # 策略A：纯动量TOP1
    def run_momentum(df):
        rets = []
        for d in df['date'].unique():
            day = df[df['date'] == d].copy()
            day = day.dropna(subset=['mom'])
            if day.empty:
                continue
            best = day.nlargest(1, 'mom')
            if not best.empty:
                rets.append({'date': d, 'ret': best.iloc[0]['mom'] / 12 if not np.isnan(best.iloc[0]['mom']) else 0})
        ret_df = pd.DataFrame(rets).dropna()
        cum = (1 + ret_df.set_index('date')['ret'] / 100).cumprod()
        ann = cum.iloc[-1] ** (252 / len(cum)) - 1
        peak = cum.cummax()
        mdd = ((cum - peak) / peak).min()
        return ann, mdd, cum
    
    for name, fscore in [('纯动量TOP1', 'mom'),
                          ('低估值动量(过滤<0.3)', 'mom'),  # 需要额外过滤
                          ('估值加权动量', None)]:
        rets = []
        for d in sorted(df['date'].unique()):
            day = df[df['date'] == d].copy()
            if day.empty or day['mom'].isna().all():
                continue
            if name == '纯动量TOP1':
                day = day.dropna(subset=['mom'])
                if day.empty: continue
                best = day.nlargest(1, 'mom')
            elif name == '低估值动量(过滤<0.3)':
                day = day.dropna(subset=['mom', 'valuation_score'])
                day = day[day['valuation_score'] < 0.4]
                if day.empty: continue
                best = day.nlargest(1, 'mom')
            else:  # 估值加权
                day = day.dropna(subset=['mom', 'valuation_score'])
                day = day.dropna(subset=['mom'])
                if day.empty: continue
                day = day.copy()
                day['score'] = day['mom'] * (1 - day['valuation_score'])
                best = day.nlargest(1, 'score')
            
            if not best.empty:
                r = best.iloc[0]['mom'] / 12  # 12周=1年动量，转为周收益
                rets.append({'date': d, 'ret': r})
        
        ret_df = pd.DataFrame(rets).dropna().set_index('date')
        if ret_df.empty:
            print(f'{name}: 无有效数据')
            continue
        cum = (1 + ret_df['ret']).cumprod()
        ann = cum.iloc[-1] ** (52 / len(cum)) - 1
        peak = cum.cummax()
        mdd = ((cum - peak) / peak).min()
        results[name] = (ann, mdd)
        print(f'{name}: 年化={ann*100:.2f}% MDD={mdd*100:.2f}%')
    
    # 策略D：纯低估
    print()
    rets = []
    for d in sorted(df['date'].unique()):
        day = df[df['date'] == d].copy()
        day = day.dropna(subset=['valuation_score'])
        if day.empty: continue
        worst = day.nsmallest(1, 'valuation_score')  # 最便宜
        if not worst.empty:
            r = worst.iloc[0]['mom'] / 12
            rets.append({'date': d, 'ret': r})
    ret_df = pd.DataFrame(rets).dropna().set_index('date')
    cum = (1 + ret_df['ret']).cumprod()
    ann = cum.iloc[-1] ** (52 / len(cum)) - 1
    peak = cum.cummax()
    mdd = ((cum - peak) / peak).min()
    print(f'纯低估TOP1: 年化={ann*100:.2f}% MDD={mdd*100:.2f}%')

print('\n完成')
