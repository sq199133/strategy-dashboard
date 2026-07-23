#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查问题ETF的原始数据"""

import akshare as ak
import numpy as np

problem_codes = ['159918', '510500']

for code in problem_codes:
    print(f"\n{'='*60}")
    print(f"检查ETF: {code}")
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
        print(f"\n前10行数据:")
        print(df.head(10))
        
        print(f"\n数据类型:")
        print(df.dtypes)
        
        # 检查date列
        print(f"\ndate列详细信息:")
        print(f"  唯一值数量: {df['date'].nunique()}")
        print(f"  NaN数量: {df['date'].isna().sum()}")
        
        # 检查是否有NaN
        if df['date'].isna().sum() > 0:
            print(f"\n⚠️ 发现NaN值！")
            print(f"NaN所在的行:")
            print(df[df['date'].isna()])
        
        # 检查date列的所有唯一值类型
        print(f"\ndate列值类型分布:")
        type_counts = df['date'].apply(lambda x: type(x).__name__).value_counts()
        print(type_counts)
        
        # 显示一些样本
        print(f"\ndate列样本值（前20个）:")
        for i, val in enumerate(df['date'].head(20)):
            print(f"  [{i}] {val} (type: {type(val).__name__})")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
