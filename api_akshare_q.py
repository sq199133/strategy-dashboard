#!/usr/bin/env python3
"""Quick AKShare remaining checks + other APIs."""
import akshare as ak

# Quick checks that don't iterate
print("=== 分红 ===")
df = ak.fund_etf_dividend_sina(symbol='sh510050')
print(f"  510050: {df.shape[0]}次分红")
print(df.tail(3).to_string())

print("\n=== 指数PE ===")
for sym in ['沪深300', '上证50', '中证500', '中证1000']:
    df = ak.stock_index_pe_lg(symbol=sym)
    print(f"  {sym}: {df.shape[0]}行, 最新PE={df['滚动市盈率'].iloc[-1]:.2f}")

print("\n=== 指数PB ===")
for sym in ['沪深300', '上证50', '中证500']:
    df = ak.stock_index_pb_lg(symbol=sym)
    print(f"  {sym}: {df.shape[0]}行, 最新PB={df.iloc[-1]['市净率']:.2f}")

print("\n=== 中证指数历史（带PE）===")
for code, name in [('000300','沪深300'),('000905','中证500'),('000688','科创50'),('399006','创业板指')]:
    df = ak.stock_zh_index_hist_csindex(symbol=code, start_date='20250101', end_date='20250612')
    print(f"  {code} {name}: {df.shape[0]}行, 最新PE={df['滚动市盈率'].iloc[-1]:.2f}")

print("\n=== ETF规模 ===")
try:
    df = ak.fund_etf_scale_sse(date='20260611')
    print(f"  上交所: {df.shape[0]}只ETF")
    print(f"  列: {list(df.columns)}")
    print(df[df['证券代码']=='510050'][['证券代码','证券简称','基金份额','基金规模']].to_string())
except Exception as e:
    print(f"  上交所: {e}")

print("\n✅ AKShare完成")
