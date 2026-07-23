"""测试美股指数和历史国际指数"""
import akshare as ak

print('=== 美股指数(Sina) ===')
for sym, name in [('.INX','标普500'),('.IXIC','纳斯达克'),('.NDX','纳指100'),('.DJI','道琼斯')]:
    try:
        df = ak.index_us_stock_sina(symbol=sym)
        print(f'  {name:<8}({sym:<8}): {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        print(f'          首:{df.iloc[0]["close"]:.2f}  末:{df.iloc[-1]["close"]:.2f}')
    except Exception as e:
        print(f'  {name:<8}({sym:<8}): ERR {str(e)[:100]}')

print()
print('=== 全球指数(东方财富) — 查有哪些 ===')
try:
    spot = ak.index_global_spot_em()
    print(f'  共{len(spot)}条')
    cols = list(spot.columns)
    print(f'  列名: {cols}')
    # 展示所有
    for _, r in spot.iterrows():
        print(f'  {r[cols[0]]:<30} {r[cols[1]]:<10} {r[cols[2]] if len(cols)>2 else ""}')
except Exception as e:
    print(f'  ERR: {str(e)[:200]}')

print()
print('=== 港股指数(Sina) ===')
try:
    df = ak.stock_hk_index_daily_sina(symbol='HSI')
    print(f'  恒生: {len(df)}行  {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
except Exception as e:
    print(f'  恒生 ERR: {str(e)[:100]}')
