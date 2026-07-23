#!/usr/bin/env python3
"""Check BaoStock, efinance, yfinance for ETF data."""
import sys, json
from datetime import datetime

# 1. BaoStock
print("=" * 65)
print("BaoStock ETF数据")
print("=" * 65)
try:
    import baostock as bs
    lg = bs.login()
    if lg.error_code == '0':
        print("  登录: ✅")
        
        # K-line data
        rs = bs.query_history_k_data_plus(
            "sh.510050",
            "date,open,high,low,close,volume,amount,adjustflag",
            start_date='2024-01-01',
            end_date='2024-06-01',
            frequency='d', adjustflag='3'
        )
        if rs.error_code == '0':
            rows = []
            while rs.next():
                rows.append(rs.get_row_data())
            print(f"  query_history_k_data: {len(rows)}行")
            print(f"  字段: date,open,high,low,close,volume,amount,adjustflag")
            print(f"  样例: {rows[0]}")
        else:
            print(f"  ❌ {rs.error_msg}")
        
        # Query stock basic (listing date, etc.)
        rs2 = bs.query_stock_basic(code="sh.510050")
        if rs2.error_code == '0':
            rows2 = []
            while rs2.next():
                rows2.append(rs2.get_row_data())
            print(f"  query_stock_basic: {rows2}")
        
        # Check if BaoStock can list all ETF codes
        rs3 = bs.query_all_stock(day=datetime.now().strftime("%Y-%m-%d"))
        if rs3.error_code == '0':
            rows3 = []
            while rs3.next():
                rows3.append(rs3.get_row_data())
            etfs = [r for r in rows3 if len(r) > 2 and 'etf' in r[2].lower() or (r[0].startswith('sh.51') or r[0].startswith('sz.15') or r[0].startswith('sz.16'))]
            print(f"  全量标的: {len(rows3)}个, 推测ETF: {len(etfs)}个")
            if etfs:
                print(f"  样例(5): {etfs[:5]}")
        else:
            print(f"  query_all_stock ❌ {rs3.error_msg}")
        
        # Check dividend
        rs4 = bs.query_dividend_data(code="sh.510050", year="2024", yearType="operate")
        if rs4.error_code == '0':
            rows4 = []
            while rs4.next():
                rows4.append(rs4.get_row_data())
            print(f"  分红数据(2024): {len(rows4)}条 -> {rows4}")
        
        # Check PE/PB
        rs5 = bs.query_stock_industry(code="sh.510050")
        if rs5.error_code == '0':
            rows5 = []
            while rs5.next():
                rows5.append(rs5.get_row_data())
            print(f"  行业: {rows5}")
        
        # Try valuation data (adjusted for ETF)
        rs6 = bs.query_adjust_factor(code="sh.510050")
        if rs6.error_code == '0':
            rows6 = []
            while rs6.next():
                rows6.append(rs6.get_row_data())
            print(f"  复权因子: {len(rows6)}条, 样例: {rows6[:2]}")
        
        bs.logout()
        print("  BaoStock: ✅ 可获取OHLCV+成交额+分红+复权因子")
    else:
        print(f"  登录失败: {lg.error_msg}")
except ImportError:
    print("  ❌ 未安装")
except Exception as e:
    print(f"  ❌ {e}")

# 2. efinance
print("\n" + "=" * 65)
print("efinance ETF数据")
print("=" * 65)
try:
    import efinance as ef
    
    # Try ETF daily data
    for sym, label in [('510050', 'A股ETF'), ('159915', 'A股ETF'), ('518880', 'A股ETF')]:
        try:
            df = ef.stock.get_quote_history(sym)
            print(f"\n  get_quote_history({sym}) {label}:")
            print(f"    结果: {df.shape[0]}行 x {df.shape[1]}列")
            print(f"    列: {list(df.columns)}")
            print(df.tail(1).to_string())
            break
        except Exception as e:
            print(f"  {sym}: {e}")
    
except ImportError:
    print("  ❌ 未安装")
except Exception as e:
    print(f"  ❌ {e}")

# 3. yfinance
print("\n" + "=" * 65)
print("yfinance ETF数据")
print("=" * 65)
try:
    import yfinance as yf
    
    # Free data - only US/international ETFs
    for sym in ['FXI', 'ASHR', 'KWEB', 'MCHI']:
        try:
            tk = yf.Ticker(sym)
            info = tk.info
            val_fields = []
            for k in ['trailingPE','forwardPE','priceToBook','dividendYield','beta',
                     'fiftyTwoWeekHigh','fiftyTwoWeekLow','averageVolume','marketCap',
                     'sharesOutstanding','returnOnEquity','revenueGrowth']:
                if k in info:
                    val_fields.append(f"{k}={info[k]}")
            hist = tk.history(period="5d")
            print(f"\n  {sym}: {info.get('shortName','')}")
            print(f"    估值: {', '.join(val_fields[:6])}")
            print(f"    历史(5日): {hist.shape[0]}行")
            print(f"    列: {list(hist.columns)}")
            break
        except Exception as e:
            print(f"  {sym}: {e}")
    
except ImportError:
    print("  ❌ 未安装")
except Exception as e:
    print(f"  ❌ {e}")

print("\n✅ 调查完毕")
