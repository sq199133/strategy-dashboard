#!/usr/bin/env python3
"""API check: AKShare ETF day frequency data."""
import importlib, inspect
from datetime import date

try:
    import akshare as ak
except ImportError:
    print("akshare 未安装")
    exit(1)

print("=" * 65)
print("AKShare - 全功能扫描")
print("=" * 65)

# 1. fund_etf_spot_em - 实时快照 (含份额/市值/资金流)
print("\n📌 fund_etf_spot_em: ETF实时行情")
print(f"   参数: {inspect.signature(ak.fund_etf_spot_em)}")
try:
    df = ak.fund_etf_spot_em()
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
except Exception as e:
    print(f"   ❌ {e}")

# 2. fund_etf_hist_em - 日级历史行情
print("\n📌 fund_etf_hist_em: ETF历史K线")
print(f"   参数: {inspect.signature(ak.fund_etf_hist_em)}")
try:
    df = ak.fund_etf_hist_em(symbol='510050', period='daily', start_date='20250101', end_date='20250612', adjust='qfq')
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
    print(df.tail(2).to_string())
except Exception as e:
    print(f"   ❌ {e}")

# 3. fund_etf_fund_daily_em - ETF基金日频
print("\n📌 fund_etf_fund_daily_em: ETF基金日频（净值）")
print(f"   参数: {inspect.signature(ak.fund_etf_fund_daily_em)}")
try:
    df = ak.fund_etf_fund_daily_em()
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
    print(df.head(3).to_string())
except Exception as e:
    print(f"   ❌ {e}")

# 4. fund_etf_fund_info_em - 基金信息
print("\n📌 fund_etf_fund_info_em: ETF基本信息")
print(f"   参数: {inspect.signature(ak.fund_etf_fund_info_em)}")
try:
    df = ak.fund_etf_fund_info_em(fund='510050')
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
except Exception as e:
    print(f"   ❌ {e}")

# 5. fund_etf_dividend_sina - 分红
print("\n📌 fund_etf_dividend_sina: ETF分红")
print(f"   参数: {inspect.signature(ak.fund_etf_dividend_sina)}")
try:
    df = ak.fund_etf_dividend_sina(symbol='sh510050')
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
    print(df.to_string())
except Exception as e:
    print(f"   ❌ {e}")

# 6. fund_etf_scale_sse/szse - 规模
print("\n📌 fund_etf_scale_sse: 上交所ETF规模")
today_str = date.today().strftime("%Y%m%d")
print(f"   参数: {inspect.signature(ak.fund_etf_scale_sse)}")
try:
    df = ak.fund_etf_scale_sse(date=today_str)
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
    print(df.head(3).to_string())
except Exception as e:
    print(f"   ❌ {e}")

print("\n📌 fund_etf_scale_szse: 深交所ETF规模")
print(f"   参数: {inspect.signature(ak.fund_etf_scale_szse)}")
try:
    df = ak.fund_etf_scale_szse(date='20250101')
    print(f"   结果: {df.shape[0]}行 x {df.shape[1]}列")
    print(f"   列: {list(df.columns)}")
    print(df.head(3).to_string())
except Exception as e:
    print(f"   ❌ {e}")

# 7. 指数PE/PB
print("\n📌 stock_index_pe_lg: 指数PE")
for sym in ['沪深300', '上证50', '中证500', '中证1000', '中证2000', '创业板指', '科创50', '上证指数']:
    try:
        df = ak.stock_index_pe_lg(symbol=sym)
        print(f"   {sym}: {df.shape[0]}行, 列={list(df.columns)[:5]}")
    except:
        pass

print("\n📌 stock_index_pb_lg: 指数PB")
for sym in ['沪深300', '上证50', '中证500', '中证1000', '中证2000']:
    try:
        df = ak.stock_index_pb_lg(symbol=sym)
        print(f"   {sym}: {df.shape[0]}行, 列={list(df.columns)[:5]}")
    except:
        pass

# 8. 中证指数历史（带PE）
print("\n📌 stock_zh_index_hist_csindex: 中证指数历史（含滚动PE）")
print(f"   参数: {inspect.signature(ak.stock_zh_index_hist_csindex)}")
indices = {
    '000300': '沪深300', '000016': '上证50', '000905': '中证500',
    '000852': '中证1000', '000688': '科创50', '399006': '创业板指',
    '000932': '中证消费', '000913': '中证医药', '000941': '新能源',
    '000985': '中证全指', '399001': '深证成指'
}
for code, name in sorted(indices.items()):
    try:
        df = ak.stock_zh_index_hist_csindex(symbol=code, start_date='20250101', end_date='20250612')
        print(f"   {code} {name}: {df.shape[0]}行, 含滚动市盈率")
        r = df.iloc[-1]
        print(f"     最新: {r['日期']} 收盘={r['收盘']} PE={r['滚动市盈率']}")
    except Exception as e:
        pass

print("\n✅ AKShare 完毕")
