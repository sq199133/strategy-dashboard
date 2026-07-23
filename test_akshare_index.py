"""Test AKShare index APIs to find fast one"""
import time
import akshare as ak

# 1. 全量指数行情 (慢但全)
print("=== stock_zh_index_spot_em (all indices) ===")
t0 = time.time()
try:
    df = ak.stock_zh_index_spot_em()
    print(f"  {len(df)} indices, cols: {list(df.columns)[:8]}")
    print(f"  Time: {time.time()-t0:.2f}s")
    # Find sh000001
    row = df[df['代码'] == '000300']
    if not row.empty:
        print(f"  000300: {row.iloc[0].to_dict()}")
except Exception as e:
    print(f"  FAIL: {e}")

# 2. 个股所属指数 (快)
print("\n=== stock_index_cons_sina (成分股所属指数) ===")
t0 = time.time()
try:
    df = ak.stock_index_cons_sina(symbol="000300")
    print(f"  {len(df)} rows, cols: {list(df.columns)[:6]}")
    print(f"  Time: {time.time()-t0:.2f}s")
except Exception as e:
    print(f"  FAIL: {e}")

# 3. 指数历史PE/PB (最有价值)
print("\n=== stock_a_indicator_lg (指数历史指标) ===")
t0 = time.time()
try:
    df = ak.stock_a_indicator_lg(symbol="000300", indicator="近5年")
    print(f"  {len(df)} rows, cols: {list(df.columns)[:8]}")
    print(f"  Time: {time.time()-t0:.2f}s")
    if not df.empty:
        print(f"  Last: {df.iloc[-1].to_dict()}")
except Exception as e:
    print(f"  FAIL: {e}")

# 4. 指数实时行情 (分市场)
print("\n=== stock_zh_index_spot (沪深) ===")
t0 = time.time()
try:
    df = ak.stock_zh_index_spot(symbol="沪深")
    print(f"  {len(df)} indices, time: {time.time()-t0:.2f}s")
    print(f"  Cols: {list(df.columns)[:8]}")
except Exception as e:
    print(f"  FAIL: {e}")
