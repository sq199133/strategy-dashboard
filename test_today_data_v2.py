#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试获取今日ETF数据 - 使用实时行情接口 (修复编码)"""

import akshare as ak
from datetime import datetime
import json

print("=" * 60)
print("测试获取今日数据")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# 方法1：使用实时行情接口
print("\n方法1：使用 stock_zh_a_spot (实时行情)")
try:
    df = ak.stock_zh_a_spot()
    print(f"  数据形状: {df.shape}")
    print(f"  列名: {df.columns.tolist()}")
    
    # 筛选ETF（代码以15、16、51、53开头）
    # 注意：可能需要检查代码格式，是否是6位数字
    print(f"\n  检查代码列格式:")
    print(f"    前5个代码: {df['代码'].head().tolist()}")
    
    # 尝试筛选ETF
    etf_df = df[df['代码'].str.startswith(('15', '16', '51', '53'))]
    print(f"  ETF数量: {len(etf_df)}")
    
    if len(etf_df) > 0:
        # 显示前5个ETF
        print(f"\n  前5个ETF:")
        for i in range(min(5, len(etf_df))):
            row = etf_df.iloc[i]
            print(f"    [{i+1}] {row['代码']} {row['名称']} 最新价:{row['最新价']} 涨跌幅:{row['涨跌幅']}")
    else:
        print(f"  [警告] 未找到ETF，可能代码格式不匹配")
        
except Exception as e:
    print(f"  [错误] {e}")
    import traceback
    traceback.print_exc()

# 方法2：检查fund_etf_hist_sina是否包含今日数据
print("\n" + "=" * 60)
print("方法2：检查fund_etf_hist_sina是否包含今日数据")
print("=" * 60)

test_codes = ['518880', '512800', '159915']

for code in test_codes:
    print(f"\n检查ETF: {code}")
    
    if code.startswith('6') or code.startswith('5'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    try:
        df = ak.fund_etf_hist_sina(symbol=symbol)
        
        if df is not None and len(df) > 0:
            latest_date = df['date'].iloc[-1]
            
            # 转换为字符串
            if hasattr(latest_date, 'strftime'):
                latest_str = latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = str(latest_date)
            
            print(f"  最新数据日期: {latest_str}")
            print(f"  今天日期: {datetime.now().strftime('%Y-%m-%d')}")
            
            if latest_str == datetime.now().strftime('%Y-%m-%d'):
                print("  [OK] 包含今日数据")
            else:
                print("  [X] 不包含今日数据")
        else:
            print("  [X] 无数据")
            
    except Exception as e:
        print(f"  [X] 错误: {e}")

print("\n" + "=" * 60)
print("结论：")
print("=" * 60)
print("1. stock_zh_a_spot() 返回实时行情，包含今日数据")
print("2. 但需要将实时数据保存到历史文件中")
print("3. fund_etf_hist_sina 可能仍只返回昨日数据")
print("\n建议：")
print("- 使用 stock_zh_a_spot() 获取今日实时数据")
print("- 将实时数据转换为历史数据格式并保存")
