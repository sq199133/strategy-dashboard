# -*- coding: utf-8 -*-
"""获取0721行情数据"""
import subprocess, json, os

# 1. 560080 中药ETF 日K
# 使用akshare获取最近数据
try:
    import akshare as ak
    import pandas as pd
    
    # 中药ETF 560080
    df = ak.fund_etf_hist_em(symbol="560080", period="daily", start_date="20260717", end_date="20260721", adjust="qfq")
    print("=== 560080 中药ETF 日K ===")
    print(df.tail(3).to_string())
    
    # 生物科技ETF 159837
    df2 = ak.fund_etf_hist_em(symbol="159837", period="daily", start_date="20260717", end_date="20260721", adjust="qfq")
    print("\n=== 159837 生物科技ETF 日K ===")
    print(df2.tail(3).to_string())
    
    # 沪深300ETF 510300
    df3 = ak.fund_etf_hist_em(symbol="510300", period="daily", start_date="20260717", end_date="20260721", adjust="qfq")
    print("\n=== 510300 沪深300ETF 日K ===")
    print(df3.tail(3).to_string())
    
    # 创业板50ETF 159949
    df4 = ak.fund_etf_hist_em(symbol="159949", period="daily", start_date="20260717", end_date="20260721", adjust="qfq")
    print("\n=== 159949 创业板50ETF 日K ===")
    print(df4.tail(3).to_string())
    
except Exception as e:
    print(f"akshare error: {e}")

# 当前策略参数
print("\n=== 策略参数 === ")
print("SCORE_W1=0.5, SCORE_W3=0.5, DEFAULT_MAX_DEV=30, DEFAULT_TOP_N=1")
print("MA21硬过滤, 去重开启, ATR_RATIO=0.85")
print("止损: 硬止损-8%/高点回撤-10% (取较宽)")
