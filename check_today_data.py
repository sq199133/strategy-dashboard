#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查AKShare API是否有2026-06-02的数据"""

import akshare as ak
from datetime import datetime

print("=" * 60)
print("检查2026-06-02数据是否可用")
print("=" * 60)

# 测试几个ETF
test_codes = ['518880', '512800', '159915']  # 黄金ETF、银行ETF、创业板ETF

for code in test_codes:
    print(f"\n检查ETF: {code}")
    
    if code.startswith('6') or code.startswith('5'):
        symbol = f'sh{code}'
    else:
        symbol = f'sz{code}'
    
    try:
        df = ak.fund_etf_hist_sina(symbol=symbol)
        
        if df is not None and len(df) > 0:
            # 检查最新的日期
            latest_date = df['date'].iloc[-1]
            print(f"  最新数据日期: {latest_date}")
            print(f"  数据类型: {type(latest_date)}")
            
            # 转换为字符串比较
            if hasattr(latest_date, 'strftime'):
                latest_str = latest_date.strftime('%Y-%m-%d')
            else:
                latest_str = str(latest_date)
            
            print(f"  最新日期(字符串): {latest_str}")
            
            if latest_str >= '2026-06-02':
                print("  ✅ 包含2026-06-02或更新的数据")
            else:
                print("  ❌ 不包含2026-06-02的数据")
            
            # 显示最后5个日期
            print(f"  最后5个日期:")
            for idx in range(max(0, len(df)-5), len(df)):
                d = df['date'].iloc[idx]
                if hasattr(d, 'strftime'):
                    d_str = d.strftime('%Y-%m-%d')
                else:
                    d_str = str(d)
                print(f"    [{idx}] {d_str}")
        else:
            print("  ❌ 无数据")
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n" + "=" * 60)
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# 检查今天是否为交易日
print("\n提示：")
print("- A股数据通常有T+1延迟")
print("- 如果今天(2026-06-02)是交易日，数据可能要明天才能获取")
print("- 如果今天不是交易日，则不会有2026-06-02的数据")
