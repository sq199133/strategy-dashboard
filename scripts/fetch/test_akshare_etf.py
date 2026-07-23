#!/usr/bin/env python3
# test_akshare_etf.py - 测试AKShare获取ETF历史数据

import akshare as ak
import pandas as pd
from datetime import datetime
import sys

# 设置标准输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def test_etf_history():
    print("=== 测试AKShare获取ETF历史数据 ===\n")
    
    # 测试ETF代码（沪深300ETF，代码510300）
    etf_code_sh = "510300"  # 上海交易所ETF
    etf_code_sz = "159792"  # 深圳交易所ETF
    
    # 测试1：上海ETF
    print(f"[测试1] 上海ETF: {etf_code_sh} (沪深300ETF)")
    print("正在下载数据...\n")
    
    try:
        # 使用 fund_etf_hist_em (东方财富数据源)
        df = ak.fund_etf_hist_em(
            symbol=etf_code_sh, 
            period="daily", 
            start_date="20000101", 
            end_date="20261231", 
            adjust=""
        )
        
        if df is not None and not df.empty:
            print(f"成功获取 {len(df)} 条数据")
            print(f"数据区间: {df['日期'].min()} ~ {df['日期'].max()}")
            print(f"\n前3条数据:")
            print(df.head(3))
            print(f"\n后3条数据:")
            print(df.tail(3))
            print(f"\n数据列: {list(df.columns)}\n")
        else:
            print("返回数据为空\n")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50 + "\n")
    
    # 测试2：深圳ETF
    print(f"[测试2] 深圳ETF: {etf_code_sz} (港股通互联网ETF)")
    print("正在下载数据...\n")
    
    try:
        df2 = ak.fund_etf_hist_em(
            symbol=etf_code_sz, 
            period="daily", 
            start_date="20000101", 
            end_date="20261231", 
            adjust=""
        )
        
        if df2 is not None and not df2.empty:
            print(f"成功获取 {len(df2)} 条数据")
            print(f"数据区间: {df2['日期'].min()} ~ {df2['日期'].max()}")
            print(f"\n前3条数据:")
            print(df2.head(3))
            print(f"\n后3条数据:")
            print(df2.tail(3))
            print(f"\n数据列: {list(df2.columns)}\n")
        else:
            print("返回数据为空\n")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_etf_history()
