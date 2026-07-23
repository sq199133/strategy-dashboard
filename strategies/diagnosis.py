# -*- coding: utf-8 -*-
"""
PE策略失败原因诊断
"""

import json
import pandas as pd
import numpy as np
import os

PE_DATA_FILE = 'D:/QClaw_Trading/data/pe_data/a_market_pe.json'
ETF_DATA_DIR = 'D:/QClaw_Trading/data/history_long'

def load_data():
    with open(PE_DATA_FILE, 'r', encoding='utf-8') as f:
        pe_data = json.load(f)
    pe_df = pd.DataFrame(pe_data)
    pe_df['date'] = pd.to_datetime(pe_df['date'])
    pe_df['pe'] = pd.to_numeric(pe_df['pe'], errors='coerce')
    
    etf_file = os.path.join(ETF_DATA_DIR, 'sh510300.json')
    with open(etf_file, 'r', encoding='utf-8') as f:
        etf_data = json.load(f)
    
    if 'records' in etf_data:
        etf_df = pd.DataFrame(etf_data['records'])
    else:
        etf_df = pd.DataFrame(etf_data)
    
    etf_df['date'] = pd.to_datetime(etf_df['date'])
    
    return pe_df, etf_df

def calc_percentile(series, window):
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    return series.rolling(window=window, min_periods=window//2).apply(rank_pct)

def main():
    print("=" * 70)
    print("PE策略失败原因诊断")
    print("=" * 70)
    
    pe_df, etf_df = load_data()
    
    # 按月聚合PE
    pe_df['year_month'] = pe_df['date'].dt.to_period('M')
    pe_monthly = pe_df.groupby('year_month').agg({'date': 'last', 'pe': 'last'}).reset_index()
    
    # 计算分位数
    pe_monthly['pe_pct_1y'] = calc_percentile(pe_monthly['pe'], 12)
    pe_monthly['pe_pct_3y'] = calc_percentile(pe_monthly['pe'], 36)
    
    # ETF月度
    etf_df['year_month'] = etf_df['date'].dt.to_period('M')
    etf_monthly = etf_df.groupby('year_month').agg({'close': 'last'}).reset_index()
    etf_monthly['returns'] = etf_monthly['close'].pct_change()
    
    # 合并
    merged = pd.merge(pe_monthly, etf_monthly, on='year_month', how='inner')
    
    print("\n" + "=" * 70)
    print("问题1: PE分位数与未来收益的关系")
    print("=" * 70)
    
    # 分组分析
    merged['pe_group'] = pd.cut(merged['pe_pct_1y'], bins=[0, 20, 40, 60, 80, 100], 
                                  labels=['Low', 'Med-Low', 'Med', 'Med-High', 'High'])
    
    # 未来1个月收益
    merged['fwd_1m'] = merged['returns'].shift(-1)
    
    group_stats = merged.groupby('pe_group').agg({
        'fwd_1m': ['mean', 'median', 'count']
    })
    
    print("\n按PE分位分组的未来1个月收益:")
    print(group_stats)
    
    # 未来3个月收益
    merged['fwd_3m'] = merged['close'].pct_change(-3)
    
    group_stats_3m = merged.groupby('pe_group').agg({
        'fwd_3m': ['mean', 'median', 'count']
    })
    
    print("\n按PE分位分组的未来3个月收益:")
    print(group_stats_3m)
    
    print("\n" + "=" * 70)
    print("问题2: PE极值点的市场表现")
    print("=" * 70)
    
    # 找出PE分位极值点
    extreme_low = merged[merged['pe_pct_1y'] <= 15]
    extreme_high = merged[merged['pe_pct_1y'] >= 85]
    
    if len(extreme_low) > 0:
        print(f"\n低估值点（PE分位<=15%）: {len(extreme_low)}个")
        print(f"  平均未来3个月收益: {extreme_low['fwd_3m'].mean():.2%}")
        print(f"  中位数未来3个月收益: {extreme_low['fwd_3m'].median():.2%}")
    
    if len(extreme_high) > 0:
        print(f"\n高估值点（PE分位>=85%）: {len(extreme_high)}个")
        print(f"  平均未来3个月收益: {extreme_high['fwd_3m'].mean():.2%}")
        print(f"  中位数未来3个月收益: {extreme_high['fwd_3m'].median():.2%}")
    
    print("\n" + "=" * 70)
    print("问题3: 相关性分析")
    print("=" * 70)
    
    # PE分位与未来收益的相关性
    corr_1m = merged['pe_pct_1y'].corr(merged['fwd_1m'])
    corr_3m = merged['pe_pct_1y'].corr(merged['fwd_3m'])
    
    print(f"\nPE分位 vs 未来1个月收益相关系数: {corr_1m:.4f}")
    print(f"PE分位 vs 未来3个月收益相关系数: {corr_3m:.4f}")
    
    # PE绝对值与未来收益的相关性
    corr_pe_1m = merged['pe'].corr(merged['fwd_1m'])
    corr_pe_3m = merged['pe'].corr(merged['fwd_3m'])
    
    print(f"\nPE绝对值 vs 未来1个月收益相关系数: {corr_pe_1m:.4f}")
    print(f"PE绝对值 vs 未来3个月收益相关系数: {corr_pe_3m:.4f}")
    
    print("\n" + "=" * 70)
    print("问题4: 市场环境变化")
    print("=" * 70)
    
    # 按年份分组
    merged['year'] = merged['date'].dt.year
    yearly_stats = merged.groupby('year').agg({
        'pe': ['mean', 'min', 'max'],
        'pe_pct_1y': 'mean',
        'returns': ['mean', 'std']
    })
    
    print("\n各年份PE和收益统计:")
    print(yearly_stats)
    
    print("\n" + "=" * 70)
    print("问题5: PE分位分布")
    print("=" * 70)
    
    print(f"\nPE分位分布:")
    print(merged['pe_pct_1y'].describe())
    
    # 画出PE分位的直方图（用文字表示）
    bins = list(range(0, 101, 10))
    hist = np.histogram(merged['pe_pct_1y'].dropna(), bins=bins)[0]
    
    print("\nPE分位直方图:")
    for i, (low, high) in enumerate(zip(bins[:-1], bins[1:])):
        bar = '#' * (hist[i] // 2)
        print(f"{low:3d}-{high:3d}%: {bar} ({hist[i]})")
    
    print("\n" + "=" * 70)
    print("诊断结论")
    print("=" * 70)
    
    # 结论性分析
    if corr_3m < -0.1:
        print("\n[+] PE分位与未来收益存在负相关，说明估值择时有一定基础")
    elif corr_3m > 0.1:
        print("\n[-] PE分位与未来收益正相关，估值择时完全失效！")
    else:
        print("\n[-] PE分位与未来收益几乎无相关，估值择时无效")
    
    low_return = extreme_low['fwd_3m'].mean() if len(extreme_low) > 0 else 0
    high_return = extreme_high['fwd_3m'].mean() if len(extreme_high) > 0 else 0
    
    if low_return > 0.05:
        print(f"[+] 低估值点买入有效（平均收益{low_return:.2%}）")
    else:
        print(f"[-] 低估值点买入无效（平均收益{low_return:.2%}）")
    
    if high_return < -0.05:
        print(f"[+] 高估值点卖出有效（未来收益{high_return:.2%}）")
    else:
        print(f"[-] 高估值点卖出无效（未来收益{high_return:.2%}）")

if __name__ == "__main__":
    main()
