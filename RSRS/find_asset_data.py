"""查找中证2000和商品指数数据源"""
import akshare as ak

# 1. 中证2000代码
print('=== 中证2000 ===')
for sym in ['sh000932','sh932000','sz399303']:
    try:
        df = ak.stock_zh_index_daily(symbol=sym)
        print(f'  {sym}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except:
        print(f'  {sym}: 未找到')

# 2. 黄金/原油 - 东方财富全球指数
print('\n=== 全球指数spot列表(部分) ===')
try:
    spot = ak.index_global_spot_em()
    print(f'  共{len(spot)}个')
    for _, r in spot.iterrows():
        name = str(r.iloc[0])
        if any(k in name for k in ['黄金','原油','布伦特','铜','天然气','白银']):
            print(f'  {name}')
except Exception as e:
    print(f'  全球指数spot: {str(e)[:100]}')

# 3. 逐一尝试商品名称
print('\n=== 商品历史数据 ===')
for sym in ['黄金','现货黄金','伦敦金','COMEX黄金','原油','布伦特原油','伦敦银']:
    try:
        df = ak.index_global_hist_em(symbol=sym)
        print(f'  {sym:<10}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except Exception as e:
        print(f'  {sym:<10}: {str(e)[:80]}')

# 4. 备用: 期货指数
print('\n=== 期货指数 ===')
for sym in ['AU','SC','CU']:
    try:
        df = ak.futures_index_ccidx(symbol=sym)
        print(f'  {sym}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
    except:
        print(f'  {sym}: 未找到')
