#!/usr/bin/env python3
"""Survey available ETF data APIs - check what each can provide."""
import sys, os, json, importlib

API_LIST = [
    ("akshare", "akshare"),
    ("baostock", "baostock"),
    ("efinance", "efinance"),
    ("yfinance", "yfinance"),
    ("zzshare", "zzshare"),
]

print("=" * 65)
print("API 可用性检查")
print("=" * 65)

available = []
for name, modname in API_LIST:
    try:
        importlib.import_module(modname)
        print(f"  ✅ {name}")
        available.append(name)
    except ImportError:
        print(f"  ❌ {name} (未安装)")

if not available:
    print("\n没有可用API，需安装")
    sys.exit(1)

print(f"\n可用: {available}")
print()

# ========= Check each API =========

# 1. AKShare - already explored some
if "akshare" in available:
    import akshare as ak
    print("=" * 65)
    print("AKShare ETF相关函数总览")
    print("=" * 65)
    
    # All ETF-related functions
    etf_funcs = [f for f in dir(ak) if 'etf' in f.lower() or 'fund_etf' in f.lower()]
    print(f"\nETF相关函数 ({len(etf_funcs)}个):")
    for f in sorted(etf_funcs):
        print(f"  {f}")
    
    # Index-related functions that might have PE/PB
    index_funcs = [f for f in dir(ak) if 'index' in f.lower() and any(s in f.lower() for s in ['pe','pb','valuation','daily','hist','spot'])]
    print(f"\n指数相关函数 ({len(index_funcs)}个):")
    for f in sorted(index_funcs):
        print(f"  {f}")
    
    # Check fund_etf_fund_daily_em parameters and output
    print(f"\n--- fund_etf_fund_daily_em ---")
    import inspect
    print(f"  参数: {inspect.signature(ak.fund_etf_fund_daily_em)}")
    try:
        df = ak.fund_etf_fund_daily_em()
        print(f"  结果: {df.shape[0]}行 x {df.shape[1]}列")
        print(f"  列: {list(df.columns)}")
        print(f"  样例:")
        print(df.head(2).to_string())
    except Exception as e:
        print(f"  ❌ {e}")

# 2. BaoStock
if "baostock" in available:
    import baostock as bs
    print("\n" + "=" * 65)
    print("BaoStock ETF数据能力")
    print("=" * 65)
    
    lg = bs.login()
    if lg.error_code == '0':
        print(f"  登录成功")
        
        # Query K-line data for an ETF
        print(f"\n--- query_history_k_data_plus ---")
        rs = bs.query_history_k_data_plus(
            "sh.510050",
            "date,open,high,low,close,volume,amount,adjustflag",
            start_date='2024-01-01',
            end_date='2024-06-01',
            frequency='d',
            adjustflag='3'
        )
        if rs.error_code == '0':
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            print(f"  结果: {len(rows)}行")
            if rows:
                print(f"  字段: date,open,high,low,close,volume,amount,adjustflag")
                print(f"  样例: {rows[0]}")
        else:
            print(f"  ❌ {rs.error_msg}")
        
        # Check if there's query stock basic info
        print(f"\n--- query_stock_basic ---")
        rs2 = bs.query_stock_basic(code="sh.510050")
        if rs2.error_code == '0':
            rows2 = []
            while rs2.next():
                rows2.append(rs2.get_row_data())
            print(f"  结果: {rows2}")
        
        bs.logout()
    else:
        print(f"  登录失败: {lg.error_msg}")

# 3. efinance
if "efinance" in available:
    import efinance as ef
    print("\n" + "=" * 65)
    print("efinance ETF数据能力")
    print("=" * 65)
    
    try:
        # Try to get ETF daily data
        df = ef.stock.get_quote_history('510050')
        print(f"\n--- get_quote_history(510050) ---")
        print(f"  结果: {df.shape[0]}行 x {df.shape[1]}列")
        print(f"  列: {list(df.columns)}")
        print(f"  样例:")
        print(df.head(2).to_string())
    except Exception as e:
        print(f"  get_quote_history ❌ {e}")
    
    # Try different symbol formats
    for sym in ['159915', 'sh510050', '510050']:
        try:
            df = ef.stock.get_quote_history(sym)
            print(f"\n--- get_quote_history('{sym}') ---")
            print(f"  结果: {df.shape[0]}行 x {df.shape[1]}列")
            print(f"  列: {list(df.columns)}")
            break
        except Exception as e:
            print(f"  {sym} ❌ {str(e)[:60]}")

# 4. yfinance
if "yfinance" in available:
    import yfinance as yf
    print("\n" + "=" * 65)
    print("yfinance ETF数据能力")
    print("=" * 65)
    
    # Check Chinese ETFs - they need .SS or .SZ suffix
    for sym in ['510050.SS', '159915.SZ', 'FXI', 'EWH', 'ASHR']:
        try:
            tk = yf.Ticker(sym)
            info = tk.info
            print(f"\n--- {sym} (yfinance) ---")
            print(f"  名称: {info.get('shortName', 'N/A')}")
            # Print all available fields that are quantitative
            interesting = ['marketCap', 'trailingPE', 'forwardPE', 'priceToBook', 'dividendYield', 
                          'fiftyTwoWeekHigh', 'fiftyTwoWeekLow', 'beta', 'volume',
                          'averageVolume', 'averageVolume10days', 'sharesOutstanding',
                          'bookValue', 'earningsQuarterlyGrowth', 'netIncomeToCommon',
                          'returnOnEquity', 'revenueGrowth', 'totalRevenue']
            for k in interesting:
                if k in info:
                    print(f"  {k}: {info[k]}")
            # Also try history
            hist = tk.history(period="5d")
            print(f"  历史数据样例:")
            print(hist.tail(2).to_string())
            break  # Just do one to avoid timeouts
        except Exception as e:
            print(f"  {sym} ❌ {str(e)[:60]}")

# 5. zzshare
if "zzshare" in available:
    import zzshare
    print("\n" + "=" * 65)
    print("zzshare ETF数据能力")
    print("=" * 65)
    
    # Check available functions
    funcs = [f for f in dir(zzshare) if not f.startswith('_')]
    print(f"  zzshare 模块: {funcs}")

print("\n✅ API调查完毕")
