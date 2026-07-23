#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试ETF数据问题"""

import akshare as ak
import pandas as pd

# 测试有问题的ETF
problem_codes = ['159918', '510500']

for code in problem_codes:
    print(f"\n{'='*60}")
    print(f"测试ETF: {code}")
    print('='*60)
    
    # 确定市场前缀
    if code.startswith('6') or code.startswith('5'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    try:
        # 获取数据
        df = ak.fund_etf_hist_sina(symbol=symbol)
        
        print(f"数据形状: {df.shape}")
        print(f"列名: {df.columns.tolist()}")
        print(f"\n前5行数据:")
        print(df.head())
        
        print(f"\n数据类型:")
        print(df.dtypes)
        
        # 检查date列
        print(f"\ndate列唯一值样本:")
        print(df['date'].unique()[:10])
        
        # 检查是否有NaN
        print(f"\nNaN检查:")
        print(f"  date列NaN数量: {df['date'].isna().sum()}")
        
        # 尝试转换
        print(f"\n尝试转换date列为字符串...")
        df['day'] = df['date'].astype(str)
        print(f"转换后day列样本: {df['day'].unique()[:5]}")
        
        # 检查是否可以比较
        print(f"\n尝试比较 '2026-05-29' >= '2026-05-29': {'2026-05-29' >= '2026-05-29'}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
