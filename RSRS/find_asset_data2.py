"""尝试更多商品/指数数据源"""
import akshare as ak

# 中证商品指数
print('=== 中证商品指数 ===')
try:
    df = ak.stock_zh_index_daily_em(symbol='csi931151')
    print(f'  中证商品(csi931151): {len(df)}行 {df.iloc[0]["日期"]} ~ {df.iloc[-1]["日期"]}')
except Exception as e:
    print(f'  csi931151: {str(e)[:80]}')

# 南华商品指数
try:
    df = ak.stock_zh_index_daily_em(symbol='sh000021')
    print(f'  南华商品(sh000021): {len(df)}行 {df.iloc[0]["日期"]} ~ {df.iloc[-1]["日期"]}')
except Exception as e:
    print(f'  南华商品: {str(e)[:80]}')

# 上证商品
try:
    df = ak.stock_zh_index_daily(symbol='sh000066')
    print(f'  上证商品(sh000066): {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
except Exception as e:
    print(f'  上证商品: {str(e)[:80]}')

# 中证黄金
for sym in ['h11018','h30017']:
    try:
        df = ak.stock_zh_index_daily_em(symbol=f'csi{sym}')
        print(f'  黄金指数(csi{sym}): {len(df)}行 {df.iloc[0]["日期"]} ~ {df.iloc[-1]["日期"]}')
    except Exception as e:
        print(f'  csi{sym}: {str(e)[:60]}')

# SHFE黄金期货主力连续
print('\n=== 期货行情 ===')
for sym in ['AU', 'SC', 'CU']:
    try:
        df = ak.futures_main_sina(symbol=sym)
        print(f'  {sym}: {len(df)}行 {df.iloc[0]["date"]} ~ {df.iloc[-1]["date"]}')
        print(f'  首:{df.iloc[0]["close"]} 末:{df.iloc[-1]["close"]}')
    except Exception as e:
        print(f'  {sym}: {str(e)[:80]}')

# 黄金ETF作为商品代理 (虽然用户不要ETF, 但黄金ETF是实物支持, 跟踪误差极小)
print('\n=== 黄金ETF===')
for sym in ['518880','159934']:
    try:
        import json, requests
        url = f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.{sym}&klt=101&fqt=1&lmt=5000'
        r = requests.get(url, timeout=10)
        data = r.json()
        kl = data['data']['klines']
        print(f'  {sym}: {len(kl)}行 {kl[0].split(",")[0]} ~ {kl[-1].split(",")[0]}')
    except Exception as e:
        print(f'  {sym}: {str(e)[:80]}')
